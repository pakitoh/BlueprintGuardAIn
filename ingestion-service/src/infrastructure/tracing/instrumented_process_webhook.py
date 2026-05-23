import time

from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.exceptions import MappingError
from src.infrastructure.metrics import webhook_duration, webhooks_received


class InstrumentedProcessWebhookUseCase(ProcessWebhookUseCase):
    async def execute(self, payload: dict, event_type: str) -> None:
        start = time.perf_counter()
        status = "accepted"
        try:
            await super().execute(payload, event_type=event_type)
        except MappingError:
            status = "rejected"
            raise
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start
            attrs = {"event_type": event_type, "status": status}
            webhooks_received.add(1, attrs)
            webhook_duration.record(duration, attrs)
