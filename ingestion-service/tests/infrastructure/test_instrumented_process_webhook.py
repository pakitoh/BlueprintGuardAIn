from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.use_cases.process_webhook import ProcessWebhookUseCase
from src.domain.exceptions import MappingError
from src.infrastructure.tracing.instrumented_process_webhook import (
    InstrumentedProcessWebhookUseCase,
)


def _use_case() -> InstrumentedProcessWebhookUseCase:
    return InstrumentedProcessWebhookUseCase(
        repository=AsyncMock(), idempotency_store=MagicMock()
    )


@pytest.mark.asyncio
async def test_delegates_to_parent_on_success(mocker):
    parent = mocker.patch.object(ProcessWebhookUseCase, "execute", AsyncMock())

    await _use_case().execute({"k": "v"}, event_type="push")

    parent.assert_awaited_once()


@pytest.mark.asyncio
async def test_reraises_mapping_error(mocker):
    mocker.patch.object(
        ProcessWebhookUseCase, "execute", AsyncMock(side_effect=MappingError("bad"))
    )

    with pytest.raises(MappingError):
        await _use_case().execute({}, event_type="push")


@pytest.mark.asyncio
async def test_reraises_unexpected_error(mocker):
    mocker.patch.object(
        ProcessWebhookUseCase, "execute", AsyncMock(side_effect=RuntimeError("boom"))
    )

    with pytest.raises(RuntimeError):
        await _use_case().execute({}, event_type="push")
