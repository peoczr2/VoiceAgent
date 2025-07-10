from __future__ import annotations

import asyncio
import base64
import json
import time
import logging
import sys
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import websockets
from openai import AsyncOpenAI

from events import (
    AudioEvent,
    OpenAIRealtimeSessionEvent,
    InputAudioTranscriptionCompletedEvent,
    InputAudioTranscriptionFailedEvent,
    TranscriptionServerEvent,
    SessionLifecycleEvent,
    make_event,
)
#from ..exceptions import STTWebsocketConnectionError, AgentsException
#from ..logger import logger

EVENT_INACTIVITY_TIMEOUT = 1000  # ms of inactivity before assuming end‑of‑stream
SESSION_CREATION_TIMEOUT = 10    # seconds
SESSION_UPDATE_TIMEOUT = 10      # seconds

DEFAULT_TURN_DETECTION = {"type": "semantic_vad"}

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

def configure_logging(log_file: str = "transcriber.log", level: int = logging.INFO) -> None:
    """Configure both file and stdout logging for this module."""
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)

    # Replace handlers if this is called multiple times
    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(sh)



@dataclass
class ErrorSentinel:
    """Wrapper around an exception for async queues."""
    error: Exception


class SessionCompleteSentinel():
    """Placed on the output queue once the websocket closes cleanly."""


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


class Transcriber:
    async def start_session(self, *args, **kwargs):
        ...


class OpenAIRealtimeTranscriber(Transcriber):
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
        self.connected: bool = False
        self._client = client
        self._model = model
        self._turn_detection = DEFAULT_TURN_DETECTION

        # Runtime state -----------------------------------------------------------------
        self._input_queue: asyncio.Queue[AudioEvent] | None = None
        self._output_queue: asyncio.Queue[Any] = asyncio.Queue()
        # expose for callers
        self.output_queue: asyncio.Queue[Any] = self._output_queue

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
        self._ws_connection_task: asyncio.Task[Any] | None = None

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
        async for message in self._websocket:
            try:
                event = make_event(json.loads(message))
                logger.debug("Received event: %s", event)

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
                await self._output_queue.put(ErrorSentinel(exc))
                raise
        await self._event_queue.put(WebsocketDoneSentinel())

    async def _configure_session(self) -> None:
        """Send session‑level configuration to the websocket."""
        assert self._websocket is not None, "Websocket not initialised"
        await self._websocket.send(
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
        )

    async def _handle_events(self) -> None:
        """
        Consume events from ``_event_queue`` and push relevant ones to
        ``_output_queue``.
        """
        while True:
            try:
                evt = await asyncio.wait_for(
                    self._event_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )
                if isinstance(evt, WebsocketDoneSentinel):
                    break

                if isinstance(evt, InputAudioTranscriptionCompletedEvent):
                    transcript = evt.transcript
                    if transcript:
                        logger.info("Transcript: %s", transcript)
                        await self._output_queue.put({"type": "transcript", "text": transcript})
                    self._end_turn(transcript)
                    self._start_turn()
                elif isinstance(evt, InputAudioTranscriptionFailedEvent):
                    logger.error("Transcription failed: %s", evt.error)
                    await self._output_queue.put(
                        ErrorSentinel(Exception(f"Transcription failed: {evt.error}"))
                    )
                else:
                    await self._output_queue.put(evt)
            except asyncio.TimeoutError:
                logger.debug("No events received for %d ms", EVENT_INACTIVITY_TIMEOUT)
                break
            except Exception as exc:
                await self._output_queue.put(ErrorSentinel(exc))
                raise
        await self._output_queue.put(SessionCompleteSentinel())
        logger.info("Event handling completed")

    async def _stream_audio(self) -> None:
        """Forward audio buffers from ``_input_queue`` to the websocket."""
        assert self._websocket is not None, "Websocket not initialised"
        assert self._input_queue is not None, "Input queue was unset"

        self._start_turn()
        while True:
            event = await self._input_queue.get()
            buffer = event.data
            if buffer is None:
                break

            self._turn_audio_buffer.append(buffer)
            try:
                logger.debug("Sending audio chunk of size %d", buffer.nbytes)
                await self._websocket.send(
                    json.dumps(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(buffer.tobytes()).decode("utf-8"),
                        }
                    )
                )
            except websockets.ConnectionClosed:
                break
            except Exception as exc:
                await self._output_queue.put(ErrorSentinel(exc))
                raise
            await asyncio.sleep(0)
        logger.info("Audio streaming completed")

    async def _handle_websocket_connection(self) -> None:
        try:
            async with websockets.connect(
                "wss://api.openai.com/v1/realtime?intent=transcription",
                additional_headers={
                    "Authorization": f"Bearer {self._client.api_key}",
                    "OpenAI-Beta": "realtime=v1",
                    "OpenAI-Log-Session": "1",
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
        except Exception as exc:
            logger.exception("Websocket connection failed")
            await self._output_queue.put(ErrorSentinel(exc))
            self._stored_exception = exc
        finally:
            await self._output_queue.put(SessionCompleteSentinel())

    async def start_session(
        self,
        input_queue: asyncio.Queue[AudioEvent],
    ) -> asyncio.Queue[Any]:
        """Begin a realtime STT session and return the output queue."""
        if self.connected:
            raise #AgentsException("Session already started")

        self._input_queue = input_queue
        logger.info("Starting transcription session")
        self._ws_connection_task = asyncio.create_task(self._handle_websocket_connection())
        return self._output_queue

    async def close(self) -> None:
        if self._ws_connection_task:
            self._ws_connection_task.cancel()
        if self._websocket:
            await self._websocket.close()
        logger.info("Transcription session closed")

async def main():
    import dotenv
    dotenv.load_dotenv()
    # Example usage
    client = AsyncOpenAI()
    transcriber = OpenAIRealtimeTranscriber(client, "whisper-1", STTModelSettings())
    
    input_queue = asyncio


if __name__ == "__main__":
    asyncio.run(main())
