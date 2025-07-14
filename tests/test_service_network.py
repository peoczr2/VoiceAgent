import asyncio
from pathlib import Path

from graph.service_network import ServiceNetwork
from graph.services.service import Service


class DummyService(Service):
    def __init__(self, name: str):
        super().__init__(name)

    async def handle(self, publisher: str, event):
        pass

    async def run(self) -> asyncio.Task:
        self.run_task = asyncio.create_task(self.start())
        return self.run_task


def test_error_handler_added_and_subscribed(tmp_path: Path):
    network = ServiceNetwork()
    svc1 = DummyService("svc1")
    svc2 = DummyService("svc2")
    network.add_service("svc1", svc1)
    network.add_service("svc2", svc2)

    log_file = tmp_path / "err.log"
    network.add_ErrorHandling(log_file=str(log_file))

    assert "svc1" in network.adjacency
    assert "error_handler" in network._services
    assert "error" in network.adjacency["svc1"]
    assert network.adjacency["svc1"]["error"] == ["error_handler"]
    assert network.adjacency["svc2"]["error"] == ["error_handler"]

    svc3 = DummyService("svc3")
    network.add_service("svc3", svc3)
    assert network.adjacency["svc3"]["error"] == ["error_handler"]
