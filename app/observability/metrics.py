from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "support_agent_requests_total",
    "Total number of chat requests handled",
    ["intent", "status"],
)

REQUEST_LATENCY = Histogram(
    "support_agent_request_latency_seconds",
    "End-to-end latency of a chat request",
    ["intent"],
)

MODEL_FALLBACK_COUNT = Counter(
    "support_agent_model_fallback_total",
    "Number of times the fallback LLM was used instead of the primary",
)

TOOL_CALL_COUNT = Counter(
    "support_agent_tool_calls_total",
    "Number of MCP tool calls made",
    ["tool_name", "status"],
)
