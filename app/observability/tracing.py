from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import get_settings

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_otel() -> TracerProvider:
    """Configures a global OpenTelemetry TracerProvider exporting spans over
    OTLP/HTTP (works with Jaeger, Grafana Tempo, or any OTLP collector you
    run for free via docker-compose)."""
    global _tracer_provider
    if _tracer_provider is not None:
        return _tracer_provider

    settings = get_settings()
    resource = Resource.create({SERVICE_NAME: settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    try:
        exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:  # noqa: BLE001
        logger.warning("OTLP exporter unavailable; spans will be created but not exported.")

    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    return provider


def get_tracer():
    return trace.get_tracer("ai-support-agent")


def get_langfuse_handler():
    """Returns a Langfuse callback handler for LangChain/LangGraph if keys
    are configured, else None (tracing is simply skipped, everything else
    still works)."""
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    from langfuse.callback import CallbackHandler

    return CallbackHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
