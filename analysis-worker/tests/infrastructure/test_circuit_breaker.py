import pytest

from src.infrastructure.llm.circuit_breaker import (
    CircuitBreakerOpenError,
    _CircuitBreakerState,
    _State,
    circuit_breaker,
)


class _Service:
    @circuit_breaker(failure_threshold=2, reset_timeout=60.0)
    async def call(self, succeed: bool = True) -> str:
        if not succeed:
            raise Exception("provider down")
        return "ok"


def a_service():
    return _Service()


@pytest.mark.asyncio
async def test_circuit_opens_after_failure_threshold():
    svc = a_service()
    with pytest.raises(Exception):
        await svc.call(succeed=False)
    with pytest.raises(Exception):
        await svc.call(succeed=False)
    with pytest.raises(CircuitBreakerOpenError):
        await svc.call(succeed=False)


@pytest.mark.asyncio
async def test_successful_call_does_not_trip_circuit():
    svc = a_service()
    assert await svc.call() == "ok"
    assert await svc.call() == "ok"
    assert not hasattr(svc, "_cb_call") or svc._cb_call.state == _State.CLOSED


@pytest.mark.asyncio
async def test_circuit_resets_after_successful_half_open_call():
    svc = a_service()
    await svc.call()  # initialise state
    svc._cb_call.state = _State.HALF_OPEN

    result = await svc.call()

    assert result == "ok"
    assert svc._cb_call.state == _State.CLOSED
    assert svc._cb_call.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_transitions_to_half_open_after_timeout(mocker):
    svc = a_service()
    await svc.call()
    svc._cb_call.state = _State.OPEN
    svc._cb_call.last_failure_time = 0.0  # expired timeout

    result = await svc.call()

    assert result == "ok"
    assert svc._cb_call.state == _State.CLOSED


@pytest.mark.asyncio
async def test_failure_count_resets_after_success():
    svc = a_service()
    with pytest.raises(Exception):
        await svc.call(succeed=False)
    assert svc._cb_call.failure_count == 1

    await svc.call()

    assert svc._cb_call.failure_count == 0


@pytest.mark.asyncio
async def test_each_method_gets_independent_state():
    class _MultiService:
        @circuit_breaker(failure_threshold=1, reset_timeout=60.0)
        async def first(self, succeed: bool = True) -> str:
            if not succeed:
                raise Exception("fail")
            return "first"

        @circuit_breaker(failure_threshold=1, reset_timeout=60.0)
        async def second(self) -> str:
            return "second"

    svc = _MultiService()
    with pytest.raises(Exception):
        await svc.first(succeed=False)
    with pytest.raises(CircuitBreakerOpenError):
        await svc.first()

    assert await svc.second() == "second"
