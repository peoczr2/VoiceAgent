

import asyncio
import pyaudio
import numpy as np
import numpy.typing as npt
from graph.services.service import Service
from events import *
import traceback

class MicrophoneService(Service):
    def __init__(self, pyaudio_instance: pyaudio.PyAudio | None = None, format=pyaudio.paInt16, channels=1, rate=16000, chunk=1024):
        super().__init__("MicrophoneService")
        if pyaudio_instance is None:
            pyaudio_instance = pyaudio.PyAudio()
        if not isinstance(pyaudio_instance, pyaudio.PyAudio):
            raise TypeError("pyaudio_instance must be an instance of pyaudio.PyAudio")
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.p = pyaudio_instance
        # self.input_device_index = input_device_index #TODO: allow setting input device index

        self.run_task: asyncio.Task | None = None
    
    async def stream_audio(self):
        """
        This method uses the computer's microphone to stream audio events.
        """
        stream = None
        try:
            print("Starting microphone stream...")
            stream = self.p.open(format=self.format,
                                    channels=self.channels,
                                    rate=self.rate,
                                    input=True,
                                    frames_per_buffer=self.chunk)
            print("Microphone stream opened.")
            while True:
                #print("Reading audio data from microphone...")
                data = await asyncio.to_thread(stream.read, self.chunk)
                data = np.frombuffer(data, dtype=np.int16)
                audio_event = AudioEvent(data=data)
                await self.publish(audio_event) #TODO: handle exceptions here
        except BaseException as e:
            print(f"An error occurred while streaming from microphone: {e}")
            traceback.print_exc()
        finally:
            if stream:
                print("Stopping microphone stream...")
                stream.stop_stream()
                stream.close()

    def run(self) -> asyncio.Task:          #TODO: consider using callback for pyaudio stream
        """
        This method uses the computer's microphone to stream audio events.
        """
        self.run_task =  asyncio.create_task(self.stream_audio())
        return self.run_task
        

class SpeakerService(Service):
    def __init__(self, pyaudio_instance: pyaudio.PyAudio | None = None, format=pyaudio.paInt16, channels=1, rate=16000, chunk=1024):
        super().__init__("SpeakerService")
        if pyaudio_instance is None:
            pyaudio_instance = pyaudio.PyAudio()
        if not isinstance(pyaudio_instance, pyaudio.PyAudio):
            raise TypeError("pyaudio_instance must be an instance of pyaudio.PyAudio")
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.p = pyaudio_instance
        # self.input_device_index = input_device_index #TODO: allow setting input device index

        self.run_task: asyncio.Task | None = None

    def convert_to_bytes(self, data: npt.NDArray[np.int16 | np.float32] | None) -> bytes:
        """
        This method converts the numpy array data to bytes.
        """
        if data is None:
            return b''
        return data.tobytes()

    async def play_audio(self):
        """
        This method plays audio events through the computer's speaker.
        """
        stream = None
        try:
            print("Starting speaker playback...", flush=True)
            stream = self.p.open(format=self.format,
                                    channels=self.channels,
                                    rate=self.rate,
                                    output=True,
                                    frames_per_buffer=self.chunk)
            print("Speaker stream opened.", flush=True)
            while True:
                #print("Waiting for audio events...", flush=True)
                publisher, event = await self._inbox.get()
                if event is None:  # End of stream signal
                    break
                data = self.convert_to_bytes(event.data)
                await asyncio.to_thread(stream.write,data)
        except BaseException as e:
            print(f"An error occurred while playing audio: {e}", flush=True)
            traceback.print_exc()
        finally:
            if stream:
                print("Stopping speaker playback...", flush=True)
                stream.stop_stream()
                stream.close()

    def run(self) -> asyncio.Task:
        """
        This method plays audio events through the computer's speaker.
        """
        self.run_task = asyncio.create_task(self.play_audio())
        return self.run_task
    
class ConsolePrintService(Service):
    """
    A simple service that prints audio events to the console.
    """
    def __init__(self):
        super().__init__("ConsolePrintService")

    async def handle(self):
        while True:
            publisher, event = await self._inbox.get()
            print(f"Received audio event from {publisher}: {event.data[:10]}...")  # Print first 10 samples
    
    def run(self) -> asyncio.Task:
        """
        This method plays audio events through the computer's speaker.
        """
        self.run_task = asyncio.create_task(self.handle())
        return self.run_task
    
# python -m graph.services.computer_media    
if __name__ == "__main__":
    async def _main():
        p = pyaudio.PyAudio()
        chunk = 128
        mic = MicrophoneService(p, chunk=chunk)
        speaker = SpeakerService(p, chunk=chunk)
        
        mic.subscribe(speaker, ["audio_chunk"])
        # Start the media control
        t1 = mic.run()
        t2 = speaker.run()

        try:
            await asyncio.gather(t1, t2)

        finally:
            p.terminate()


    asyncio.run(_main())







































"""class MediaChannel:
    def __init__(self, handled_intput_event_types: list[type] = [], emitted_output_event_types: list[type] = []):
        self.in_queue: asyncio.Queue[MediaEvent] = asyncio.Queue()
        self.out_queue: asyncio.Queue[MediaEvent] = asyncio.Queue()

        if not all(isinstance(t, type) for t in handled_intput_event_types):
            raise ValueError("handled_event_types must be a list of types")
        if not all(isinstance(t, type) for t in emitted_output_event_types):
            raise ValueError("handled_event_types must be a list of types")
        
        self.handled_intput_event_types = handled_intput_event_types
        self.emitted_output_event_types = emitted_output_event_types

    def get_in_queue(self) -> asyncio.Queue[MediaEvent]:
        return self.in_queue
    def get_out_queue(self) -> asyncio.Queue[MediaEvent]:
        return self.out_queue
    def set_in_queue(self, in_queue: asyncio.Queue[MediaEvent]) -> None:
        self.in_queue = in_queue
    def set_out_queue(self, out_queue: asyncio.Queue[MediaEvent]) -> None:
        self.out_queue = out_queue

    def get_handled_intput_event_types(self) -> list[type]:
        return self.handled_intput_event_types
    def get_emitted_output_event_types(self) -> list[type]:
        return self.emitted_output_event_types
    
    def run(self):
        raise NotImplementedError("MediaChannel subclasses must implement the run method")"""
