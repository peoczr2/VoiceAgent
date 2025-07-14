import logging
import asyncio
from typing import Any

from graph.services.service import Service


def _configure_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger(f"LoggingService[{log_file}]")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(fh)
    return logger


class LoggingService(Service):
    """Service that logs every received event."""

    def __init__(self, log_file: str = "events.log") -> None:
        super().__init__("LoggingService")
        self.logger = _configure_logger(log_file)

    async def handle(self, publisher: str, event: Any) -> None:
        self.logger.info("%s -> %s", publisher, event)

    async def run(self) -> asyncio.Task:
        self.run_task = asyncio.create_task(self.start())
        return self.run_task
