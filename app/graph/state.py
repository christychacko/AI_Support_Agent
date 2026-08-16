from __future__ import annotations

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages

from app.schemas import (
    EscalationResult,
    OrderStatusResult,
    RagAnswer,
    RouteDecision,
    TicketResult,
)


class AgentState(TypedDict):
    """Shared state threaded through every node in the graph.

    `messages` uses LangGraph's `add_messages` reducer so each node can just
    append and the full conversation history is preserved automatically by
    the checkpointer (this is our "memory").
    """

    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str

    route: Optional[RouteDecision]
    rag_result: Optional[RagAnswer]
    order_result: Optional[OrderStatusResult]
    ticket_result: Optional[TicketResult]
    escalation_result: Optional[EscalationResult]

    final_text: Optional[str]
