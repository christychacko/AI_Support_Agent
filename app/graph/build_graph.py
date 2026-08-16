from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    escalation_node,
    finalize_node,
    order_tool_node,
    rag_node,
    ticket_tool_node,
)
from app.graph.router import route_edge, route_node
from app.graph.state import AgentState
from app.memory.checkpointer import get_checkpointer


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", route_node)
    graph.add_node("rag", rag_node)
    graph.add_node("order_tool", order_tool_node)
    graph.add_node("ticket_tool", ticket_tool_node)
    graph.add_node("escalation", escalation_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_edge,
        {
            "rag": "rag",
            "order_tool": "order_tool",
            "ticket_tool": "ticket_tool",
            "escalation": "escalation",
        },
    )
    for leaf in ("rag", "order_tool", "ticket_tool", "escalation"):
        graph.add_edge(leaf, "finalize")
    graph.add_edge("finalize", END)

    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
