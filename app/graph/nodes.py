from __future__ import annotations

import logging
import uuid

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import get_settings
from app.graph.llm import get_model_router
from app.graph.state import AgentState
from app.schemas import (
    EscalationResult,
    OrderStatusResult,
    RagAnswer,
    TicketResult,
)
from app.tools.mcp_client import get_mcp_client
from app.tools.rag_tool import retrieve

logger = logging.getLogger(__name__)


def _last_user_text(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


# ---------------------------------------------------------------------------
# RAG node
# ---------------------------------------------------------------------------

RAG_SYSTEM_PROMPT = """You are a support assistant. Answer the user's question
using ONLY the provided context snippets. If the context doesn't contain the
answer, say you don't have that information and set grounded=false.
Always cite which source(s) you used."""


def rag_node(state: AgentState) -> dict:
    query = _last_user_text(state)
    hits = retrieve(query, k=4)

    context = "\n\n".join(f"[{h['source']}]: {h['text']}" for h in hits) or "No relevant documents found."

    llm = get_model_router().get(structured_schema=RagAnswer)
    messages = [
        SystemMessage(content=RAG_SYSTEM_PROMPT),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {query}"),
    ]
    result: RagAnswer = llm.invoke(messages)
    return {
        "rag_result": result,
        "final_text": result.answer,
        "messages": [AIMessage(content=result.answer)],
    }


# ---------------------------------------------------------------------------
# Order status node (MCP tool call)
# ---------------------------------------------------------------------------

async def order_tool_node(state: AgentState) -> dict:
    order_id = state["route"].order_id
    if not order_id:
        text = "I couldn't find an order number in your message -- could you share it (e.g. #1002)?"
        return {"order_result": None, "final_text": text, "messages": [AIMessage(content=text)]}

    client = get_mcp_client()
    raw = await client.call_tool("order_lookup", {"order_id": order_id})
    result = OrderStatusResult(**raw)

    if result.found:
        eta_clause = f", expected {result.eta}" if result.eta else ""
        text = f"Order #{result.order_id} is currently **{result.status}**{eta_clause}."
    else:
        text = f"I couldn't find an order with ID #{order_id}. Could you double-check the number?"

    return {"order_result": result, "final_text": text, "messages": [AIMessage(content=text)]}


# ---------------------------------------------------------------------------
# Ticket node (MCP tool call)
# ---------------------------------------------------------------------------

async def ticket_tool_node(state: AgentState) -> dict:
    summary = _last_user_text(state)
    client = get_mcp_client()
    raw = await client.call_tool("create_ticket", {"summary": summary, "user_id": state["user_id"]})
    result = TicketResult(**raw)

    text = (
        f"I'm sorry for the trouble. I've opened ticket **{result.ticket_id}** "
        f"for our team to follow up on this."
    )
    return {"ticket_result": result, "final_text": text, "messages": [AIMessage(content=text)]}


# ---------------------------------------------------------------------------
# Human escalation node
# ---------------------------------------------------------------------------

async def escalation_node(state: AgentState) -> dict:
    settings = get_settings()
    escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    reason = state["route"].reasoning

    notified = False
    if settings.escalation_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=5) as http_client:
                await http_client.post(
                    settings.escalation_webhook_url,
                    json={"text": f"[{escalation_id}] Human needed for user {state['user_id']}: {reason}"},
                )
            notified = True
        except Exception:  # noqa: BLE001
            logger.exception("Failed to notify escalation webhook")
    else:
        logger.info("ESCALATION %s: %s", escalation_id, reason)

    result = EscalationResult(escalation_id=escalation_id, reason=reason, notified=notified)
    text = (
        f"I've escalated this to a human agent (reference **{escalation_id}**). "
        "Someone will follow up with you shortly."
    )
    return {"escalation_result": result, "final_text": text, "messages": [AIMessage(content=text)]}


# ---------------------------------------------------------------------------
# Finalize node -- always runs last
# ---------------------------------------------------------------------------

def finalize_node(state: AgentState) -> dict:
    # No-op passthrough: final_text/route/etc are already set by upstream
    # nodes. This node exists as a single, stable "exit point" so the graph
    # always converges to one place before we build the AgentResponse.
    return {}
