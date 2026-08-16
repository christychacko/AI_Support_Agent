"""
Structured Pydantic contracts used across the graph.

Every node that touches the LLM either consumes or produces one of these
models, so the FastAPI layer can always guarantee a validated JSON shape
back to the client -- never raw, unstructured text.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    KNOWLEDGE_QUESTION = "knowledge_question"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    HUMAN_NEEDED = "human_needed"


class RouteDecision(BaseModel):
    """Structured output of the router node."""

    intent: Intent = Field(..., description="Best-matching category for the user's message")
    confidence: float = Field(..., ge=0, le=1, description="Router's confidence in this classification")
    reasoning: str = Field(..., description="One sentence explaining the classification")
    order_id: Optional[str] = Field(None, description="Order id mentioned by the user, if any")


class Citation(BaseModel):
    source: str
    snippet: str


class RagAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    grounded: bool = Field(..., description="Whether the answer was actually supported by retrieved docs")


class OrderStatusResult(BaseModel):
    order_id: str
    status: str
    eta: Optional[str] = None
    found: bool


class TicketResult(BaseModel):
    ticket_id: str
    status: str = "open"
    summary: str


class EscalationResult(BaseModel):
    escalation_id: str
    reason: str
    notified: bool


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str


class AgentResponse(BaseModel):
    """The single structured payload guaranteed to leave the graph."""

    session_id: str
    intent: Intent
    message: str
    rag: Optional[RagAnswer] = None
    order: Optional[OrderStatusResult] = None
    ticket: Optional[TicketResult] = None
    escalation: Optional[EscalationResult] = None
    trace_id: Optional[str] = None
