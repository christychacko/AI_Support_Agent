from __future__ import annotations

import json
import logging
import time

from fastapi import FastAPI
from fastapi.responses import Response
from langchain_core.messages import HumanMessage
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette.sse import EventSourceResponse

from app.graph.build_graph import get_graph
from app.observability.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.observability.tracing import get_langfuse_handler, get_tracer, setup_otel
from app.schemas import AgentResponse, ChatRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Support Agent", version="1.0.0")

setup_otel()

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
except Exception:  # noqa: BLE001
    logger.warning("FastAPI OTel auto-instrumentation unavailable.")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _build_response(session_id: str, final_state: dict, trace_id: str | None) -> AgentResponse:
    route = final_state["route"]
    return AgentResponse(
        session_id=session_id,
        intent=route.intent,
        message=final_state.get("final_text", ""),
        rag=final_state.get("rag_result"),
        order=final_state.get("order_result"),
        ticket=final_state.get("ticket_result"),
        escalation=final_state.get("escalation_result"),
        trace_id=trace_id,
    )


@app.post("/chat")
async def chat(request: ChatRequest):
    """Streams the agent's progress as SSE events, ending with one
    structured AgentResponse JSON object validated by Pydantic."""

    graph = get_graph()
    tracer = get_tracer()
    langfuse_handler = get_langfuse_handler()
    config = {
        "configurable": {"thread_id": request.session_id},
        "callbacks": [langfuse_handler] if langfuse_handler else [],
    }

    async def event_generator():
        start = time.time()
        trace_id = None
        status = "success"
        intent_label = "unknown"
        try:
            with tracer.start_as_current_span("chat_request") as span:
                span.set_attribute("user_id", request.user_id)
                span.set_attribute("session_id", request.session_id)
                trace_id = format(span.get_span_context().trace_id, "032x")

                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                }

                final_state = None
                async for event in graph.astream(inputs, config=config, stream_mode="updates"):
                    for node_name, node_output in event.items():
                        yield {
                            "event": "progress",
                            "data": json.dumps({"node": node_name}),
                        }
                        final_state = node_output if final_state is None else {**final_state, **node_output}

                # pull the full final state from the checkpointer (covers
                # fields set by earlier nodes not present in the last delta)
                snapshot = await graph.aget_state(config)
                full_state = snapshot.values

                intent_label = full_state["route"].intent.value
                response = _build_response(request.session_id, full_state, trace_id)

                yield {
                    "event": "final",
                    "data": response.model_dump_json(),
                }
        except Exception:
            status = "error"
            logger.exception("Error handling chat request")
            yield {
                "event": "error",
                "data": json.dumps({"error": "internal_error"}),
            }
        finally:
            REQUEST_COUNT.labels(intent=intent_label, status=status).inc()
            REQUEST_LATENCY.labels(intent=intent_label).observe(time.time() - start)

    return EventSourceResponse(event_generator())
