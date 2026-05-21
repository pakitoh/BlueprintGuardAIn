from opentelemetry import metrics

_meter = metrics.get_meter("blueprintguardain.action")

results_processed = _meter.create_counter(
    name="blueprintguardain_results_processed",
    description="Number of analysis results processed",
    unit="1",
)

action_duration = _meter.create_histogram(
    name="blueprintguardain_action_duration_seconds",
    description="Time to process an analysis result and execute all actions",
    unit="s",
)

pipeline_duration = _meter.create_histogram(
    name="blueprintguardain_pipeline_duration_seconds",
    description="End-to-end time from CodeChange ingestion to actions executed",
    unit="s",
)
