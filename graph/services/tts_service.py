from __future__ import annotations

import sys
import io
import asyncio
from typing import Any, AsyncIterator

import numpy as np
import numpy.typing as npt
from openai import AsyncOpenAI

from graph.services.service import Service
from events import TTSEvent, AudioEvent, ErrorEvent, TextEvent


class TTSService(Service):
    """Abstract base class for text-to-speech services."""

    def __init__(self, name: str = "TTSService", stream: bool = True) -> None:
        super().__init__(name)
        self.stream = stream
        if stream:
            self.TTS = self.stream_audio
        else:
            self.TTS = self.send_audio
        self.curr_tts_task: asyncio.Task | None = None
        

    async def synthesize(self, text: str):
        """Convert ``text`` to a PCM int16 numpy array."""
        raise NotImplementedError("Subclasses must implement synthesize() method.")
    async def synthesize_stream(self, text: str) -> AsyncIterator[npt.NDArray[np.int16]]:
        """Yield PCM int16 numpy array chunks for the given text."""
        raise NotImplementedError("Subclasses must implement synthesize_stream() method.")
    
    async def send_audio(self, text: str) -> None:
        """Send synthesized audio for the given text."""
        audio_data = await self.synthesize(text)
        await self.publish(AudioEvent(data=audio_data))
    async def stream_audio(self, text: str) -> None:
        """Stream audio chunks for the given text."""
        logger.info("Streaming audio for text: %s", text)
        async for chunk in self.synthesize_stream(text):
            await self.publish(AudioEvent(data=chunk))    
    

    async def handle(self, publisher: str, event: Any) -> None:
        logger.info("Handling event in TTSService: %s", event)
        try:
            match event:
                case TextEvent(text=text):
                    logger.info("stream: %s", self.stream)
                    if self.stream:
                        if self.curr_tts_task and not self.curr_tts_task.done():
                            self.curr_tts_task.cancel()
                        logger.info("Received TextEvent: %s", text)
                        self.curr_tts_task = asyncio.create_task(self.TTS(text))
                        await self.curr_tts_task
                #TODO: Handle InterruptEvent to stop streaming
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Error in TTSService: {exc}")
            await self.publish(ErrorEvent(error=str(exc)))
        # ignore unrelated events

    async def run(self) -> asyncio.Task:
        logger.info("Starting TTSService...")
        self.run_task = asyncio.create_task(self.start())
        return self.run_task


class OpenAITTSService(TTSService):
    """TTSService implementation using the OpenAI API."""

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini-tts", voice: str = "alloy", stream: bool = True) -> None:
        super().__init__(name="OpenAITTSService", stream = stream)
        self._client = client
        self._model = model
        self._voice = voice

    async def synthesize(self, text: str) -> npt.NDArray[np.int16]:
        """Return the full synthesized audio for ``text`` as a PCM array."""
        logger.info("Synthesize for text: %s", text)
        response = await self._client.audio.speech.with_streaming_response.create(
            input=text,
            model=self._model,
            voice=self._voice,
            response_format="pcm",
        )
        chunks: list[bytes] = []
        async for chunk in response.iter_bytes():
            chunks.append(chunk)
        audio_bytes = b"".join(chunks)
        return np.frombuffer(audio_bytes, dtype=np.int16)
    async def synthesize_stream(self, text: str):
        logger.info("synthesize_stream for text: %s", text)
        response = await self._client.audio.speech.with_streaming_response.create(
            input=text,
            model=self._model,
            voice=self._voice,
            response_format="pcm",
        )
        leftover = b""
        async for chunk in response.iter_bytes():
            chunk = leftover + chunk
            if len(chunk) % 2 != 0:
                # Save the last byte for the next chunk
                leftover = chunk[-1:]
                chunk = chunk[:-1]
            else:
                leftover = b""
            if chunk:
                yield np.frombuffer(chunk, dtype=np.int16)
        # Optionally handle any leftover at the end (shouldn't happen for well-formed streams)
        

# ---------------------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------------------- 
import logging
logger = logging.getLogger(__name__)
def configure_logging(log_file: str = "tests/log_files/tts_service.log", level: int = logging.INFO) -> None:
    """Configure both file and stdout logging for this module."""
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(formatter)
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)

    # Replace handlers if this is called multiple times
    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(sh)

# python -m graph.services.tts_service
if __name__ == "__main__":
    from graph.services.computer_media import MicrophoneService, ConsolePrintService, SpeakerService
    from graph.services.transcriber import OpenAIRealtimeTranscriber
    from graph.services.service import Echo
    import pyaudio
    configure_logging()  
    async def _test1():
        import dotenv
        dotenv.load_dotenv()
        aclient = AsyncOpenAI()              
        tts = OpenAITTSService(aclient, model="gpt-4o-mini-tts", voice="nova")
        p = pyaudio.PyAudio()
        chunk = 1024
        speaker = SpeakerService(p, chunk=chunk)
        con = ConsolePrintService()
        echo = Echo()

        echo.subscribe(tts, ["text"])
        echo.subscribe(con, ["text"])
        tts.subscribe(speaker, ["audio_chunk"])
        t2 = speaker.run()
        t3 = con.run()
        t4 = tts.run()
        await echo.publish(TextEvent(text="Hello, this is a test of the OpenAI TTS service."))

        try:
            await asyncio.gather(t2, t3, t4)

        finally:
            p.terminate()

    async def _test3(): 
        import dotenv
        dotenv.load_dotenv()
        aclient = AsyncOpenAI()              
        tts = OpenAITTSService(aclient, model="gpt-4o-mini-tts", voice="nova")
        

        p = pyaudio.PyAudio()
        chunk = 1024
        mic = MicrophoneService(p, chunk=chunk)
        speaker = SpeakerService(p, chunk=chunk)
        con = ConsolePrintService()
        trans = OpenAIRealtimeTranscriber(aclient, model="gpt-4o-mini-transcribe")
        
        tts.subscribe(speaker, ["audio_chunk"])
        mic.subscribe(trans, ["audio_chunk"])
        trans.subscribe(con, ["text"])
        trans.subscribe(tts, ["text"])
        # Start the media control
        t1 = mic.run()
        t2 = speaker.run()
        t3 = trans.run()
        t4 = tts.run()

        try:
            await asyncio.gather(t1, t2, t3, t4)

        finally:
            p.terminate()


    asyncio.run(_test1())