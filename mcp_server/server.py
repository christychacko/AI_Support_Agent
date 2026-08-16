"""
A standalone MCP server exposing two tools to any MCP client:

  - order_lookup(order_id: str) -> order status from a SQLite "orders" table
  - create_ticket(summary: str, user_id: str) -> creates a support ticket

Run standalone for debugging:
    python mcp_server/server.py

In production it's spawned over stdio by app/tools/mcp_client.py, which is
how LangGraph nodes call these tools -- this keeps "the thing that talks to
your real order database" fully decoupled from the agent/orchestration code,
exactly as MCP is meant to be used: swap this file for a connector to your
real DB/CRM and nothing in app/graph/ has to change.
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "support.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("support-tools")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            eta TEXT
        );
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
        );
        """
    )
    # seed a few demo orders if the table is empty
    if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO orders (order_id, status, eta) VALUES (?, ?, ?)",
            [
                ("1001", "delivered", None),
                ("1002", "in_transit", "2026-08-20"),
                ("1003", "processing", "2026-08-22"),
            ],
        )
    conn.commit()
    conn.close()


_init_db()


@mcp.tool()
def order_lookup(order_id: str) -> dict:
    """Look up the shipping status of an order by its order_id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT order_id, status, eta FROM orders WHERE order_id = ?", (order_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return {"order_id": order_id, "status": "not_found", "eta": None, "found": False}
    return {"order_id": row["order_id"], "status": row["status"], "eta": row["eta"], "found": True}


@mcp.tool()
def create_ticket(summary: str, user_id: str) -> dict:
    """Create a support ticket for a complaint or issue that needs follow-up."""
    ticket_id = f"TCK-{uuid.uuid4().hex[:8].upper()}"
    conn = _get_conn()
    conn.execute(
        "INSERT INTO tickets (ticket_id, user_id, summary, status) VALUES (?, ?, ?, 'open')",
        (ticket_id, user_id, summary),
    )
    conn.commit()
    conn.close()
    return {"ticket_id": ticket_id, "status": "open", "summary": summary}


if __name__ == "__main__":
    mcp.run(transport="stdio")
