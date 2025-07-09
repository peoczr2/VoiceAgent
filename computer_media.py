from media_control import MediaControl
from events import *
import asyncio
import pyaudio
import numpy as np
import numpy.typing as npt

class ComputerMediaControl(MediaControl):
    """
    A class to use computer's microphone and speaker.
    This class extends MediaControl and implements methods to handle media events.
    """

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

    async def convert_audio_chunk(self, audio_chunk) -> npt.NDArray[np.int16 | np.float32] | None:
        """
        This method converts the audio chunk to a numpy array.
        """
        if audio_chunk is None:
            return None
        return np.frombuffer(audio_chunk, dtype=np.int16)

    async def stream_incoming_media(self):
        """
        This method uses the computer's microphone to stream audio events.
        """
        print("Starting microphone stream...")
        stream = self.p.open(format=self.format,
                                channels=self.channels,
                                rate=self.rate,
                                input=True,
                                frames_per_buffer=self.chunk)
        print("Microphone stream opened.")
        try:
            while True:
                data = await asyncio.to_thread(stream.read, self.chunk)
                data = await self.convert_audio_chunk(data)
                await self.input_queue.put(AudioEvent(data=data))
        except Exception as e:
            print(f"An error occurred while streaming from microphone: {e}")
            self._stored_exception = e
        finally:
            stream.stop_stream()
            stream.close()

    async def convert_to_bytes(self, data: npt.NDArray[np.int16 | np.float32] | None) -> bytes:
        """
        This method converts the numpy array data to bytes.
        """
        if data is None:
            return b''
        return data.tobytes()
    
    async def stream_outgoing_audio(self):
        """
        This method uses the computer's speaker to play the streamed audio events.
        """
        print("Starting speaker stream...")
        try:
            print("Opening speaker stream...")
            stream = self.p.open(format=self.format,
                                channels=self.channels,
                                rate=self.rate,
                                output=True,
                                frames_per_buffer=self.chunk)
            print("Speaker stream opened.")
        except Exception as e:
            print(f"An error occurred while opening speaker stream: {e}")
            self._stored_exception = e
            return
        try:
            while True:
                media_event = await self.output_queue.get()
                await asyncio.to_thread(stream.write, await self.convert_to_bytes(media_event.data))
        finally:
            stream.stop_stream()
            stream.close()
    async def stream_outgoing_text(self):
        while True:
            text = await self.output_text_queue.get()
            print(f"Output Text: {text}")

    async def handle_output_events(self):
        """
        This method handles the output events from the output queue.
        It checks for errors and cleans up tasks if necessary.
        """
        self.speaker_task = asyncio.create_task(self.stream_outgoing_audio())
        self.console_task = asyncio.create_task(self.stream_outgoing_text())
        while True:
            event = await self.output_queue.get()
            match event:
                case AudioEvent(data=data):
                    await self.output_audio_queue.put(event)
                case TextEvent(text=text):
                    await self.output_text_queue.put(text)

    
    def _check_errors(self):
        if self.microphone_task and self.microphone_task.done():
            exc = self.microphone_task.exception()
            if exc and isinstance(exc, Exception):
                self._stored_exception = exc

        if self.speaker_task and self.speaker_task.done():
            exc = self.speaker_task.exception()
            if exc and isinstance(exc, Exception):
                self._stored_exception = exc

    def _cleanup_tasks(self):
        if self.microphone_task and not self.microphone_task.done():
            self.microphone_task.cancel()

        if self.speaker_task and not self.speaker_task.done():
            self.speaker_task.cancel()

    async def run(self, output_stream: asyncio.Queue[AudioEvent] | None = None) -> None:
        """
        This method runs the media control, processing the output stream.
        It simulates playing audio from the computer's speaker.
        """
        if output_stream is  not None:
            self.output_queue = output_stream
            
        self.microphone_task = asyncio.create_task(self.stream_incoming_media())
        self.output_task = asyncio.create_task(self.handle_output_events())
        try:
            while True:
                await asyncio.sleep(2)
        except KeyboardInterrupt:
            print("KeyboardInterrupt received, stopping tasks...")
        finally:
            self._cleanup_tasks()
            self.p.terminate()

async def _main():
    computer = ComputerMediaControl()
    output_queue = asyncio.Queue[AudioEvent]()
    
    # Start the media control
    comp_task = asyncio.create_task( computer.run(output_stream=output_queue))
    await comp_task

    
    
if __name__ == "__main__":
    asyncio.run(_main())
