from abc import ABC, abstractmethod
from typing import AsyncIterator
import asyncio
from events import *

class MediaControl(ABC):
    def __init__(self):
        self.input_queue: asyncio.Queue[MediaEvent] = asyncio.Queue()
        self.output_queue: asyncio.Queue[MediaEvent] = asyncio.Queue()

    def get_input_queue(self) -> asyncio.Queue[MediaEvent]:
        return self.input_queue
    
    def set_output_queue(self, output_queue: asyncio.Queue[MediaEvent]) -> None:
        self.output_queue = output_queue

    @abstractmethod
    async def stream_incoming_media(self) -> None:
        pass

    @abstractmethod
    async def run(self, output_queue: asyncio.Queue[MediaEvent] | None = None) -> None:
        pass


import asyncio
from typing import Any, Dict, List

Event = Dict[str, Any]

class Service:
    def __init__(self, name: str):
        self.name = name
        # This service’s own queue of incoming events:
        self._inbox: asyncio.Queue[Event] = asyncio.Queue()
        # For events *I* emit, map event_type → list of subscriber queues
        self._subscribers: Dict[str, List[asyncio.Queue[Event]]] = {}

    def subscribe_to(self, publisher: "Service", event_types: List[str]):
        """
        Subscribe *this* service to specific event_types from *publisher*.
        """
        for evt in event_types:
            publisher._subscribers.setdefault(evt, []).append(self._inbox)

    async def publish(self, event_type: str, event: Event):
        """
        Emit an event: push it straight into each subscriber’s inbox.
        """
        for q in self._subscribers.get(event_type, []):
            q.put_nowait((self.name, event))

    async def start(self):
        """
        Run loop: pull from my inbox and handle each event.
        """
        while True:
            publisher_name, ev = await self._inbox.get()
            try:
                await self.handle(publisher_name, ev)
            except Exception:
                # isolate failures
                ...

    async def handle(self, publisher: str, event: Event):
        """
        Override in subclasses to react to events.
        """
        raise NotImplementedError






















"""class ComputerMediaControl(MediaControl):
    """
    """A class to use computer's microphone and speaker.
    This class extends MediaControl and implements methods to handle media events."""
    """
    def __init__(self, media_channels: list[MediaChannel] = []):
        """"""
        Initializes the ComputerMediaControl with input and output channels.
        """"""
        super().__init__()
        self.input_channels = input_channels
        self.input_channel_tasks: list[asyncio.Task] = []
        self.output_channels = output_channels
        self.output_subscriptions: dict[type, list[asyncio.Queue]] = {}
        self.media_channels = media_channels
        self.media_channels_tasks: list[asyncio.Task] = []


    def __init__(self, format=pyaudio.paInt16, channels=1, rate=16000, chunk=1024):
        super().__init__()
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.p = pyaudio.PyAudio()
        self.microphone_task = None
        self.speaker_task = None
        self._stored_exception = None


        self.output_audio_queue: asyncio.Queue[AudioEvent] = asyncio.Queue()
        self.output_text_queue: asyncio.Queue[str] = asyncio.Queue()

    async def subscribe_output_channels(self):
        for channel in self.media_channels:
            if isinstance(channel, MediaChannel):
                output_queue = channel.get_in_queue()
                if output_queue is not None:
                    for event_type in channel.get_handled_intput_event_types():
                        if event_type not in self.output_subscriptions:
                            self.output_subscriptions[event_type] = []
                        self.output_subscriptions[event_type].append(output_queue)
                else:
                    raise ValueError("MediaChannel must have a valid input queue")# TODO: could be more specific, which channel is missing output queue
            else:
                raise ValueError(f"Unsupported MediaChannel type: {type(channel)}")


    async def convert_audio_chunk(self, audio_chunk) -> npt.NDArray[np.int16 | np.float32] | None:
        """
        This method converts the audio chunk to a numpy array.
        """
        if audio_chunk is None:
            return None
        return np.frombuffer(audio_chunk, dtype=np.int16)

    async def convert_to_bytes(self, data: npt.NDArray[np.int16 | np.float32] | None) -> bytes:
        """
        This method converts the numpy array data to bytes.
        """
        if data is None:
            return b''
        return data.tobytes()
    
    async def start_channels(self):
        """
        This method starts the input channels.
        """
        for channel in self.media_channels:
            if isinstance(channel, MediaChannel):
                channel.set_in_queue(self.input_queue)
                self.media_channels_tasks.append(asyncio.create_task(channel.run()))
            else:
                raise ValueError(f"Unsupported input channel type: {type(channel)}")

    async def dispatch(self, event: MediaEvent):
        """
        This method dispatches the event to the appropriate output channels.
        """
        queues = self.output_subscriptions.get(type(event), [])
        if not queues:
            return
        await asyncio.gather(*(q.put(event) for q in queues))
    async def handle_output_events(self):
        """
        This method handles the output events from the output queue.
        It checks for errors and cleans up tasks if necessary.
        """
        while True:
            event = await self.output_queue.get()
            await self.dispatch(event)
    
    def _check_errors(self):
        for task in self.media_channels_tasks:
            if task and task.done():
                exc = task.exception()
                if exc and isinstance(exc, Exception):
                    self._stored_exception = exc

    def _cleanup_tasks(self):
        for task in self.media_channels_tasks:
            if task and not task.done():
                task.cancel()
        
    async def run(self, output_queue: asyncio.Queue[MediaEvent] | None = None, channels: list[MediaChannel] = []) -> None:
        """
        This method runs the media control, processing the output stream.
        It simulates playing audio from the computer's speaker.
        """
        if output_queue is  not None:
            self.output_queue = output_queue
        
        self.channels = channels
        await self.subscribe_output_channels()

        self.output_stream_task = asyncio.create_task(self.handle_output_events())
        await self.start_handling_input_events()

        try:
            while True:
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            print("KeyboardInterrupt received, stopping tasks...")
        finally:
            self._cleanup_tasks()
            self.p.terminate()

"""
