import logging
import asyncio

from dataclasses import dataclass
from typing import Any

from .service import Service
from events import ErrorEvent


def _configure_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger(f"ErrorHandlerService[{log_file}]")
    logger.setLevel(logging.ERROR)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(fh)
    return logger


class ErrorHandlerService(Service):
    """Simple service that logs :class:`ErrorEvent` instances to a file."""

    def __init__(self, log_file: str = "errors.log") -> None:
        super().__init__("ErrorHandlerService")
        self.logger = _configure_logger(log_file)

    async def handle(self, publisher: str, event: Any) -> None:
        """Log errors coming from other services."""
        if isinstance(event, ErrorEvent):
            self.logger.error("%s: %s", publisher, event.error)
        else:
            self.logger.error("%s: %s", publisher, event)

    async def run(self) -> asyncio.Task:
        self.run_task = asyncio.create_task(self.start())
        return self.run_task
