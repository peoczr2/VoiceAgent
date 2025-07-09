from abc import ABC, abstractmethod
from typing import AsyncIterator
import asyncio
from events import *

class MediaControl(ABC):
    def __init__(self):
        self.input_queue: asyncio.Queue[AudioEvent] = asyncio.Queue()
        self.output_queue: asyncio.Queue[AudioEvent] = asyncio.Queue()

    def get_input_queue(self) -> asyncio.Queue[AudioEvent]:
        return self.input_queue
    
    def set_output_queue(self, output_queue: asyncio.Queue[AudioEvent]) -> None:
        self.output_queue = output_queue

    @abstractmethod
    async def stream_incoming_media(self) -> None:
        pass

    @abstractmethod
    async def run(self, output_queue: asyncio.Queue[AudioEvent] | None = None) -> None:
        pass
