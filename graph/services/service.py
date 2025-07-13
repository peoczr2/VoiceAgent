import asyncio
from typing import List, Dict, Literal

from dataclasses import dataclass
from events import register_event

@register_event
@dataclass
class ServiceLifecycleEvent:
    """Base class for service lifecycle events."""
    type: Literal['service.done'] = 'service.done'

class Service:
    def __init__(self, name: str):
        self.name = name
        self._inbox = asyncio.Queue()
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self.run_task: asyncio.Task | None = None

    async def start(self):
        while True:
            publisher, event = await self._inbox.get()
            await self.handle(publisher, event)

    async def publish(self, event): #TODO: maybe have a base Event class
        """Publisher notifies all subscribers of this event_type."""
        event_type = event.type
        for q in self._subscribers.get(event_type, []):
            q.put_nowait((self.name, event))

    async def handle(self, publisher: str, event: dict):
        raise NotImplementedError

    def subscribe(self, subscriber, event_types: List[str]):
        """
        Register another service as a subscriber to my events.
        """
        for evt in event_types:
            self._subscribers.setdefault(evt, []).append(subscriber._inbox)

    async def run(self) -> asyncio.Task:
        """
        Start the service's main loop.
        This should be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement run() method.")
