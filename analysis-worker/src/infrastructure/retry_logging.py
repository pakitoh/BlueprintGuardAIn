from collections.abc import Callable
from typing import Any

import structlog
from tenacity import RetryCallState

logger = structlog.get_logger()


def make_retry_logger(event: str) -> Callable[[RetryCallState], None]:
    def log_retry(rs: RetryCallState) -> None:
        err: Any = rs.outcome.exception() if rs.outcome is not None else None
        logger.warning(event, attempt=rs.attempt_number, error=str(err))

    return log_retry
