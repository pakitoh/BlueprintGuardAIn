import asyncio
import structlog

logger = structlog.get_logger()


async def main():
    logger.info("action_worker_starting")
    # Kafka consumption loop
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
