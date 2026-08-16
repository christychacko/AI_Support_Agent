from __future__ import annotations

import pathlib

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import get_settings

_saver: SqliteSaver | None = None
_cm = None  # keeps the underlying sqlite3 connection context manager alive


def get_checkpointer() -> SqliteSaver:
    """Returns a process-wide SqliteSaver so every session_id (LangGraph
    'thread') persists its full message history between HTTP requests --
    this is the agent's conversation memory, and it costs nothing but disk.
    """
    global _saver, _cm
    if _saver is None:
        settings = get_settings()
        db_path = pathlib.Path(settings.checkpoint_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _cm = SqliteSaver.from_conn_string(str(db_path))
        _saver = _cm.__enter__()
    return _saver
