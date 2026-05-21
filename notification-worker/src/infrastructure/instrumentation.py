import logging
import os
import subprocess
import structlog
import sys
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
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler

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


def add_otel_trace_id(_, __, event_dict):
    span = trace.get_current_span()
    if not span.is_recording():
        return event_dict
    span_context = span.get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    add_otel_trace_id,
    structlog.processors.format_exc_info,
]


def setup_resource() -> Resource:
    return Resource.create({
        "service.name": settings.app_name,
        "service.version": resolve_commit_sha(),
    })


def setup_logging(resource):
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    for name, level in {"aiokafka": logging.INFO, "asyncio": logging.INFO}.items():
        logging.getLogger(name).setLevel(level)

    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(
                endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
            )
        )
    )

    structlog.configure(
        processors=SHARED_PROCESSORS
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    otel_handler = LoggingHandler(logger_provider=provider)
    otel_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=SHARED_PROCESSORS,
        )
    )
    root_logger.addHandler(otel_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=SHARED_PROCESSORS,
        )
    )
    root_logger.addHandler(console_handler)

    LoggingInstrumentor().instrument(set_logging_format=False)
    logger.debug("logging_initialized", service_name=settings.app_name)


def setup_tracing(resource):
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
            )
        )
    )
    trace.set_tracer_provider(tracer_provider)


def setup_metrics(resource):
    metrics.set_meter_provider(
        MeterProvider(
            resource=resource,
            metric_readers=[
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(
                        endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
                    )
                )
            ],
        )
    )


def instrument_app():
    resource = setup_resource()
    setup_logging(resource)
    setup_tracing(resource)
    setup_metrics(resource)
    AIOKafkaInstrumentor().instrument()
    logger.debug("app_instrumentation_complete")
