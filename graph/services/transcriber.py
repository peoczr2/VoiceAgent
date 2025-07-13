from __future__ import annotations

import asyncio
import base64
import json
import time
import logging
import sys
import io
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import websockets
from openai import AsyncOpenAI

from graph.services.service import Service, ServiceLifecycleEvent
from events import *
#from ..exceptions import STTWebsocketConnectionError, AgentsException
#from ..logger import logger

EVENT_INACTIVITY_TIMEOUT = 1000  # ms of inactivity before assuming end‑of‑stream
SESSION_CREATION_TIMEOUT = 10    # seconds
SESSION_UPDATE_TIMEOUT = 10      # seconds
WEBSOCKET_SEND_TIMEOUT = 30      # seconds

DEFAULT_TURN_DETECTION = {"type": "server_vad",
  "threshold": 0.5,
  "prefix_padding_ms": 300,
  "silence_duration_ms": 500,}
#{"type": "semantic_vad",} #TODO: test out semantic vad, it is a bit tricky as it requires intent in my speech to detect the end of a turn

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


class AgentsException(Exception):
    """Generic exception for transcriber-related errors."""


def configure_logging(log_file: str = "transcriber.log", level: int = logging.INFO) -> None:
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

# ---------------------------------------------------------------------------
# Transcription Events
# ---------------------------------------------------------------------------
# TODO: consoder seperating openai events from the rest of the events

class WebsocketDoneSentinel:
    """Internal marker pushed on _event_queue once the websocket iterator finishes."""


async def _wait_for_event[EventT](
    event_queue: asyncio.Queue[EventT],
    expected: list[str] | list[type[EventT]],
    timeout: float,
) -> EventT:
    """Wait until an event of one of the expected types appears."""
    start = time.time()
    while True:
        rem = timeout - (time.time() - start)
        if rem <= 0:
            raise TimeoutError(f"Timeout waiting for event(s): {expected}")
        evt = await asyncio.wait_for(event_queue.get(), timeout=rem)
        if isinstance(expected[0], type):
            if any(isinstance(evt, cls) for cls in expected):
                return evt
        else:
            if getattr(evt, 'type', '') in expected:
                return evt
        if getattr(evt, 'type', '') == 'error':
            raise


class OpenAIRealtimeTranscriber(Service):
    """
    Establishes an OpenAI realtime STT websocket, streams audio buffers from
    ``input_queue``, and yields transcription events back to callers via an
    :class:`asyncio.Queue`.
    """

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str
    ):
        super().__init__(name="OpenAIRealtimeTranscriber")
        self.connected: bool = False
        self._client = client
        self._model = model
        self._turn_detection = DEFAULT_TURN_DETECTION

        self._inbox#: asyncio.Queue[AudioEvent] = asyncio.Queue() #TODO: when events are properly setup, this should be reiterated

        self._websocket: websockets.ClientConnection | None = None
        self._event_queue: asyncio.Queue[
            TranscriptionServerEvent | WebsocketDoneSentinel
        ] = asyncio.Queue()
        self._state_queue: asyncio.Queue[SessionLifecycleEvent] = asyncio.Queue()
        self._turn_audio_buffer: list[npt.NDArray[np.int16 | np.float32]] = []

        # Tasks -------------------------------------------------------------------------
        self._listener_task: asyncio.Task[Any] | None = None
        self._process_events_task: asyncio.Task[Any] | None = None
        self._stream_audio_task: asyncio.Task[Any] | None = None

        # Error propagation -------------------------------------------------------------
        self._stored_exception: Exception | None = None

    # --------------------------------------------------------------------- helpers ----
    def _start_turn(self) -> None:
        """Mark the beginning of a speech turn."""
        self._turn_audio_buffer = []

    def _end_turn(self, _transcript: str) -> None:
        """End a speech turn – placeholder kept for parity with upstream codebase."""
        self._turn_audio_buffer = []

    async def _event_listener(self) -> None:
        """
        Iterate the websocket and stick every event JSON onto ``_event_queue`` (and
        ``_state_queue`` for lifecycle events).
        """
        assert self._websocket is not None, "Websocket not initialised"
        print("Starting event listener")
        async for message in self._websocket:
            try:
                raw = message
                logger.info("Received raw message: %s", raw)
                payload = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from WS: {e} — skipping frame")
                continue
            try:
                event = make_event(payload)
                logger.info("Received event: %s", event)

                if isinstance(event, OpenAIRealtimeSessionEvent):
                    await self._state_queue.put(event)

                if isinstance(
                    event,
                    (
                        OpenAIRealtimeSessionEvent,
                        InputAudioTranscriptionCompletedEvent,
                        InputAudioTranscriptionFailedEvent,
                    ),
                ):
                    await self._event_queue.put(event)
            except Exception as exc:
                logger.error(f"Error processing event: {exc}")
                await self.publish(ErrorEvent(error=str(exc)))
                raise
        await self._event_queue.put(WebsocketDoneSentinel())

    async def _configure_session(self) -> None:
        """Send session‑level configuration to the websocket."""
        assert self._websocket is not None, "Websocket not initialised"
        print("Configuring session with model:", self._model)
        logger.info("Turn detection settings: %s", self._turn_detection)
        await asyncio.wait_for(
            self._websocket.send(
                json.dumps(
                    {
                        "type": "transcription_session.update",
                        "session": {
                            "input_audio_format": "pcm16",
                            "input_audio_transcription": {"model": self._model},
                            "turn_detection": self._turn_detection,
                        },
                    }
                )
            ),
            timeout=SESSION_UPDATE_TIMEOUT,
        )
        print("Session configured")

    async def _handle_events(self) -> None:
        """
        Consume events from ``_event_queue`` and push relevant ones to
        ``_output_queue``.
        """
        while True:
            try:
                """evt = await asyncio.wait_for(
                    self._event_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )"""
                evt = await self._event_queue.get()
                if isinstance(evt, WebsocketDoneSentinel):
                    break

                if isinstance(evt, InputAudioTranscriptionCompletedEvent):
                    transcript = evt.transcript
                    if transcript:
                        logger.info("Transcript: %s", transcript)
                        text_event = TextEvent(text=transcript)
                        await self.publish(text_event)
                    self._end_turn(transcript)
                    self._start_turn()
                elif isinstance(evt, InputAudioTranscriptionFailedEvent):
                    logger.error("Transcription failed: %s", evt.error)
                    await self.publish(
                        ErrorEvent(error=f"Transcription failed: {evt.error}")
                    )
                else:
                    await self.publish(evt) # TODO handle this
            except asyncio.TimeoutError:
                logger.info("No events received for %d ms", EVENT_INACTIVITY_TIMEOUT)
                break
            except Exception as exc:
                await self.publish(ErrorEvent(error=str(exc)))
                raise
        #TODO: consider adding a final event to signal the end of processing
        logger.info("Event handling completed")

    async def _stream_audio(self) -> None:
        """Forward audio buffers from ``_input_queue`` to the websocket."""
        assert self._websocket is not None, "Websocket not initialised"
        assert self._inbox is not None, "_inbox was unset"

        self._start_turn()
        while True:
            pub, event = await self._inbox.get()
            buffer = event.data
            if buffer is None:
                print("Received no audio data, maybe error maybe not")
                break

            self._turn_audio_buffer.append(buffer)
            try:
                #logger.info("Sending audio chunk of size %d", buffer.nbytes)
                await asyncio.wait_for(
                    self._websocket.send(
                        json.dumps(
                            {
                                "type": "input_audio_buffer.append",
                                "audio": base64.b64encode(buffer.tobytes()).decode("utf-8"),
                            }
                        )
                    ),
                    timeout=WEBSOCKET_SEND_TIMEOUT,
                )
            except websockets.ConnectionClosed:
                break
            except asyncio.CancelledError:
                break
            except (OSError, ConnectionResetError) as e:
                logger.error(f"Network error sending audio buffer: {e}, retrying…")
                await asyncio.sleep(0.5)
                continue
            except Exception as exc:
                await self.publish(ErrorEvent(error=str(exc)))
                raise
            await asyncio.sleep(0)
        logger.info("Audio streaming completed")

    async def _handle_websocket_connection(self) -> None:
        try:
            logger.info(f"Authorization: Bearer {self._client.api_key}")
            async with websockets.connect(
                "wss://api.openai.com/v1/realtime?intent=transcription",
                additional_headers={
                    "Authorization": f"Bearer {self._client.api_key}",
                    "OpenAI-Beta": "realtime=v1",
                },
            ) as ws:
                self._websocket = ws
                logger.info("Websocket connection established")

                # Listener & handshake
                self._listener_task = asyncio.create_task(self._event_listener())
                await _wait_for_event(
                    self._state_queue,
                    ["session.created", "transcription_session.created"],
                    SESSION_CREATION_TIMEOUT,
                )
                await self._configure_session()
                await _wait_for_event(
                    self._state_queue,
                    ["session.updated", "transcription_session.updated"],
                    SESSION_UPDATE_TIMEOUT,
                )

                # Worker tasks
                self._process_events_task = asyncio.create_task(self._handle_events())
                self._stream_audio_task = asyncio.create_task(self._stream_audio())

                self.connected = True
                logger.info("Realtime transcription websocket established")

                await asyncio.gather(
                    self._listener_task,
                    self._process_events_task,
                    self._stream_audio_task,
                )
        except asyncio.CancelledError:
            self.connected = False
        #except websocket.InvalidStatusCode as e:
        #    logger.error(f"WebSocket handshake failed ({e.status_code}): {e}")
        #    await self.publish(ErrorEvent(error=str(e)))
        #    self._stored_exception = e
        except Exception as exc:
            logger.exception("Websocket connection failed")
            await self.publish(ErrorEvent(error=str(exc)))
            self._stored_exception = exc
        finally:
            await self.publish(ServiceLifecycleEvent())

    def run(self) -> asyncio.Task:
        """Begin a realtime STT session and return the output queue."""
        if self.connected:
            raise AgentsException("Realtime transcription session already running")

        logger.info("Starting transcription session")
        self.run_task = asyncio.create_task(self._handle_websocket_connection())
        return self.run_task

    async def close(self) -> None:
        if self._stream_audio_task:
            self._stream_audio_task.cancel()
        if self._listener_task:
            self._listener_task.cancel()
        if self._process_events_task:
            self._process_events_task.cancel()

        if self.run_task:
            self.run_task.cancel()
        if self._websocket:
            await self._websocket.close()
        logger.info("Transcription session closed")



# python -m graph.services.transcriber
if __name__ == "__main__":
    from graph.services.computer_media import MicrophoneService, ConsolePrintService, SpeakerService
    import pyaudio
    async def _main():
        configure_logging()
        import dotenv
        dotenv.load_dotenv()
        aclient = AsyncOpenAI()
        trans = OpenAIRealtimeTranscriber(aclient, model="gpt-4o-mini-transcribe")

        p = pyaudio.PyAudio()
        chunk = 1024
        mic = MicrophoneService(p, chunk=chunk)
        speaker = SpeakerService(p, chunk=chunk)
        con = ConsolePrintService()
        
        mic.subscribe(speaker, ["audio_chunk"])
        mic.subscribe(trans, ["audio_chunk"])
        trans.subscribe(con, ["text"])
        # Start the media control
        t1 = mic.run()
        t2 = speaker.run()
        t3 = trans.run()

        try:
            await asyncio.gather(t1, t2, t3)

        finally:
            p.terminate()


    asyncio.run(_main())