import logging.config
import structlog
from opentelemetry import trace, metrics, _logs
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

from src.config import settings

logger = structlog.get_logger()


def add_otel_trace_id(logger, method_name, event_dict):
    """Processor that adds the current OTEL trace_id and span_id to the log event."""
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def setup_logging():
    """Configures global logging using dictConfig for maximum robustness."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_otel_trace_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    resource = Resource.create({"service.name": settings.otel_service_name})
    logger_provider = LoggerProvider(resource=resource)
    _logs.set_logger_provider(logger_provider)

    exporter = OTLPLogExporter(
        endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    logging_config = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
            "otel": {
                "class": "opentelemetry.instrumentation.logging.handler.LoggingHandler",
                "level": "NOTSET",
                "logger_provider": logger_provider,
                "formatter": "json",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "otel"],
                "level": settings.log_level.upper(),
            },
        },
    }

    logging.config.dictConfig(logging_config)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger.debug("logging_initialized", service_name=settings.otel_service_name)


def instrument_app():
    """Sets up OpenTelemetry tracing and metrics instrumentation."""
    resource = Resource.create({"service.name": settings.otel_service_name})

    tp = TracerProvider(resource=resource)
    tp.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
            )
        )
    )
    trace.set_tracer_provider(tp)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    )
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[reader])
    )

    logger.debug("app_instrumentation_complete")
