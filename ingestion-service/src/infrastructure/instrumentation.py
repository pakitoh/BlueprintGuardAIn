import logging
import os
import subprocess
import structlog
import sys
import time
from opentelemetry import trace, metrics
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.aiokafka import AIOKafkaInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from starlette.middleware.base import BaseHTTPMiddleware

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


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Adds access logging."""

    async def dispatch(self, request, call_next):
        init_time = time.perf_counter()
        response = await call_next(request)
        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - init_time) * 1000, 2),
        )
        return response


def _add_otel_trace_id(_, __, event_dict):
    """Processor that adds the current OTEL trace_id and span_id to the log event."""
    span = trace.get_current_span()
    if not span.is_recording():
        event_dict["span"] = None
        return event_dict
    span_context = span.get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


# Single Source of Truth for Log Formatting
SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    _add_otel_trace_id,
    structlog.processors.format_exc_info,
]


def _setup_logging(resource, app):
    """Configures global logging with native OTEL bridge."""

    # Configure logging levels
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    overrides = {
        "aiokafka": logging.INFO,
        "asyncio": logging.INFO,
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
        processors=SHARED_PROCESSORS
        + [
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

    # Access log
    app.add_middleware(AccessLogMiddleware)

    logger.debug("logging_initialized", service_name=settings.app_name)


uvicorn_log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {},
    "handlers": {},
    "loggers": {
        "uvicorn": {"propagate": True},
        "uvicorn.error": {"propagate": False},
        "uvicorn.access": {"propagate": False},
    },
}


def _setup_tracing(resource):
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)


def _setup_metrics(resource):
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[reader])
    )


def _setup_resource() -> Resource:
    return Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": resolve_commit_sha(),
        }
    )


def instrument_app(app):
    """Sets up network-level observability (Logs, Traces & Metrics)."""
    resource = _setup_resource()
    _setup_logging(resource, app)
    _setup_tracing(resource)
    _setup_metrics(resource)
    FastAPIInstrumentor.instrument_app(app)
    AIOKafkaInstrumentor().instrument()
    logger.debug("app_instrumentation_complete")
