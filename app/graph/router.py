from __future__ import annotations

from langchain_core.messages import SystemMessage

from app.graph.llm import get_model_router
from app.graph.state import AgentState
from app.schemas import RouteDecision

ROUTER_SYSTEM_PROMPT = """You are a routing classifier for a customer support system.
Classify the user's latest message into exactly one intent:

- knowledge_question: general questions answerable from docs (policies, how-to, FAQ)
- order_status: user wants status/tracking/ETA of a specific order
- complaint: user is unhappy, wants a refund, or reports a problem that needs a ticket
- human_needed: user explicitly asks for a human, or the issue is sensitive/urgent
  (fraud, legal threat, extreme anger, safety issue)

Extract an order_id if one is mentioned (e.g. "#1002" -> "1002"). Respond only
through the structured schema provided."""


def route_node(state: AgentState) -> dict:
    llm = get_model_router().get(structured_schema=RouteDecision)
    messages = [SystemMessage(content=ROUTER_SYSTEM_PROMPT)] + state["messages"]
    decision: RouteDecision = llm.invoke(messages)
    return {"route": decision}


def route_edge(state: AgentState) -> str:
    """Conditional edge function LangGraph uses to pick the next node."""
    intent = state["route"].intent
    return {
        "knowledge_question": "rag",
        "order_status": "order_tool",
        "complaint": "ticket_tool",
        "human_needed": "escalation",
    }[intent.value]
