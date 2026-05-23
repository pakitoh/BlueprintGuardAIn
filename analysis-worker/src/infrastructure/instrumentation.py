import logging
import os
import subprocess
import sys
from typing import Any

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.config import settings

logger = structlog.get_logger()


def resolve_commit_sha() -> str:
    if sha := os.environ.get("GIT_SHA"):
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _add_otel_trace_id(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Processor that adds the current OTEL trace_id and span_id to the log event."""
    span = trace.get_current_span()
    if not span.is_recording():
        return event_dict
    span_context = span.get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


# Single Source of Truth for Log Formatting
SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    _add_otel_trace_id,
    structlog.processors.format_exc_info,
]


def _setup_logging(resource: Resource) -> None:
    """Configures global logging with native OTEL bridge."""

    # Configure logging levels
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    overrides = {
        "aiokafka": logging.INFO,
        "asyncio": logging.INFO,
        "LiteLLM": logging.ERROR,
        "LiteLLM Router": logging.ERROR,
    }
    for name, level in (overrides or {}).items():
        logging.getLogger(name).setLevel(level)

    # Setup OpenTelemetry
    provider = LoggerProvider(resource=resource)
    exporter = OTLPLogExporter(
        endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
    )
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    # Configure Structlog
    structlog.configure(
        processors=[
            *SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # OTEL Handler
    otel_handler = LoggingHandler(logger_provider=provider)
    json_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=SHARED_PROCESSORS,
    )
    otel_handler.setFormatter(json_formatter)
    root_logger.addHandler(otel_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
        foreign_pre_chain=SHARED_PROCESSORS,
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Bridge for libraries that don't use standard propagation
    LoggingInstrumentor().instrument(set_logging_format=False)

    logger.debug("logging_initialized", service_name=settings.app_name)


def _setup_tracing(resource: Resource) -> None:
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)


def _setup_metrics(resource: Resource) -> None:
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[reader])
    )


def _setup_litellm_otel() -> None:
    """Enable LiteLLM's built-in OTEL callback.

    LiteLLM uses the globally configured TracerProvider (set up in setup_tracing),
    so spans for every LLM/embedding call are automatically nested under the
    current active span and share the same trace_id.
    """
    import litellm

    litellm.callbacks = ["otel"]


def _setup_langfuse() -> None:
    """Register a Langfuse span processor on the global TracerProvider.

    No-op if credentials are not set. Langfuse's processor applies a default
    filter that exports only LLM-related spans (gen_ai.* attributes), so our
    Kafka/HTTP spans continue to flow only to the local OTEL collector.
    """
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("langfuse_disabled", reason="credentials_not_set")
        return

    from langfuse import Langfuse

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        release=resolve_commit_sha(),
    )
    logger.info("langfuse_enabled", host=settings.langfuse_host)


def _setup_resource() -> Resource:
    return Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": resolve_commit_sha(),
        }
    )


def instrument_app() -> None:
    """Sets up network-level observability (Logs, Traces & Metrics)."""
    resource = _setup_resource()
    _setup_logging(resource)
    _setup_tracing(resource)
    _setup_metrics(resource)
    AIOKafkaInstrumentor().instrument()
    _setup_litellm_otel()
    _setup_langfuse()
    logger.debug("app_instrumentation_complete")


def flush_langfuse() -> None:
    """Flush pending Langfuse spans. Safe to call when Langfuse is disabled."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as e:
        logger.warning("langfuse_flush_failed", error=str(e))
