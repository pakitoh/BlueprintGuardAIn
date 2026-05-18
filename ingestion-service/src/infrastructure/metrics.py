from opentelemetry import metrics

_meter = metrics.get_meter("blueprintguardain.ingestion")

webhooks_received = _meter.create_counter(
    name="blueprintguardain_webhooks_received",
    description="Number of GitHub webhooks received",
    unit="1",
)

webhook_duration = _meter.create_histogram(
    name="blueprintguardain_webhook_duration_seconds",
    description="Time to validate and publish a webhook to Kafka",
    unit="s",
)
