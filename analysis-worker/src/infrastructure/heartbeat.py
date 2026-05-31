import asyncio
from pathlib import Path

import structlog

logger = structlog.get_logger()


class Heartbeat:
    """Periodically touches a file so the container HEALTHCHECK can detect a
    live event loop, independent of message traffic."""

    def __init__(self, path: str, interval_seconds: float):
        self._path = Path(path)
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._touch()
        self._task = asyncio.create_task(self._run())
        logger.debug("heartbeat_started", path=str(self._path), interval=self._interval)

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        logger.debug("heartbeat_stopped")

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            self._touch()

    def _touch(self) -> None:
        try:
            self._path.touch()
        except OSError as e:
            logger.warning("heartbeat_touch_failed", path=str(self._path), error=str(e))
