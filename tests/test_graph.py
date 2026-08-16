"""
Lightweight smoke tests that don't require a live GROQ_API_KEY:
they check that the graph compiles and that Pydantic schemas validate
correctly. Add live end-to-end tests once you have API keys wired into CI.
"""
from app.schemas import (
    AgentResponse,
    Intent,
    OrderStatusResult,
    RouteDecision,
)


def test_route_decision_schema():
    decision = RouteDecision(
        intent=Intent.ORDER_STATUS,
        confidence=0.92,
        reasoning="User asked about their order.",
        order_id="1002",
    )
    assert decision.intent == Intent.ORDER_STATUS
    assert decision.order_id == "1002"


def test_agent_response_schema():
    response = AgentResponse(
        session_id="s1",
        intent=Intent.ORDER_STATUS,
        message="Your order is in transit.",
        order=OrderStatusResult(order_id="1002", status="in_transit", found=True),
    )
    dumped = response.model_dump_json()
    assert "in_transit" in dumped


def test_graph_builds():
    # Import lazily -- this will fail fast and clearly if wiring is broken,
    # without needing network access or an API key.
    from app.graph.build_graph import build_graph

    graph = build_graph()
    assert graph is not None
