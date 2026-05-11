import logging
import structlog
from opentelemetry import trace, metrics, _logs
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from src.config import settings

logger = structlog.get_logger()

def setup_observability():
    """Sets up OpenTelemetry tracing, metrics, logs, and log correlation."""
    
    resource = Resource.create({
        "service.name": settings.otel_service_name,
    })

    # --- Tracing & Metrics Setup (unchanged) ---
    tracer_provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    span_processor = BatchSpanProcessor(otlp_trace_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    otlp_metric_exporter = OTLPMetricExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(otlp_metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # --- Logging Setup ---
    logger_provider = LoggerProvider(resource=resource)
    _logs.set_logger_provider(logger_provider)
    otlp_log_exporter = OTLPLogExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
    
    # Define common processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # ProcessorFormatter allows us to format standard library logs (e.g. from aiokafka)
    # the same way as structlog logs.
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    # Bridge standard logging to OTEL
    otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    otel_handler.setFormatter(formatter)
    
    # Console handler for local visibility
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # Clear existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(otel_handler)
    root_logger.addHandler(console_handler)
    
    # Set log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    console_handler.setLevel(log_level)

    # --- Structlog Configuration ---
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Log correlation
    LoggingInstrumentor().instrument(set_logging_format=False)

    logger.debug("observability_initialized", 
                endpoint=settings.otel_exporter_otlp_endpoint,
                service_name=settings.otel_service_name)
