import asyncio
from pathlib import Path

from graph.services.error_handler_service import ErrorHandlerService
from events import ErrorEvent


def test_error_logged(tmp_path: Path):
    log_file = tmp_path / "err.log"
    svc = ErrorHandlerService(log_file=str(log_file))
    asyncio.run(svc.handle("tester", ErrorEvent(error="boom")))
    assert log_file.exists()
    text = log_file.read_text()
    assert "boom" in text
