import asyncio
from pathlib import Path

from graph.services.logging_service import LoggingService
from events import TextEvent


def test_logging_service_logs_event(tmp_path: Path):
    log_file = tmp_path / "events.log"
    svc = LoggingService(log_file=str(log_file))
    asyncio.run(svc.handle("tester", TextEvent(text="hello")))
    assert log_file.exists()
    text = log_file.read_text()
    assert "hello" in text
