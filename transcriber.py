from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import websockets
from openai import AsyncOpenAI

from events import *
#from ..exceptions import STTWebsocketConnectionError, AgentsException
#from ..logger import logger

EVENT_INACTIVITY_TIMEOUT = 1000  # ms of inactivity before assuming end‑of‑stream
SESSION_CREATION_TIMEOUT = 10    # seconds
SESSION_UPDATE_TIMEOUT = 10      # seconds

DEFAULT_TURN_DETECTION = {"type": "semantic_vad"}


@dataclass
class ErrorSentinel:
    """Wrapper around an exception for async queues."""
    error: Exception


class SessionCompleteSentinel():
    """Placed on the output queue once the websocket closes cleanly."""


class WebsocketDoneSentinel:
    """Internal marker pushed on _event_queue once the websocket iterator finishes."""


async def _wait_for_event(
    event_queue: asyncio.Queue[dict[str, Any]],
    expected_types: list[str],
    timeout: float,
) -> dict[str, Any]:
    """
    Block until an event appears on *event_queue* whose ``type`` is in *expected_types*.

    Raises
    ------
    TimeoutError
        If *timeout* seconds elapse without receiving the event.
    """
    start_time = time.time()
    while True:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            raise TimeoutError(f"Timeout waiting for event(s): {expected_types}")
        evt = await asyncio.wait_for(event_queue.get(), timeout=remaining)
        evt_type = evt.get("type", "")
        if evt_type in expected_types:
            return evt
        elif evt_type == "error":
            raise #STTWebsocketConnectionError(f"Error event: {evt.get('error')}")


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
        self._event_queue: asyncio.Queue[dict[str, Any] | WebsocketDoneSentinel] = asyncio.Queue()
        self._state_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
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

    # ------------------------------------------------------------- websocket plumbing ----
    async def _event_listener(self) -> None:
        """
        Iterate the websocket and stick every event JSON onto ``_event_queue`` (and
        ``_state_queue`` for lifecycle events).
        """
        assert self._websocket is not None, "Websocket not initialised"
        async for message in self._websocket:
            try:
                event = json.loads(message)

                evt_type = event.get("type", "")
                if evt_type == "error":
                    raise# STTWebsocketConnectionError(f"Error event: {event.get('error')}")

                if evt_type in {
                    "session.updated",
                    "transcription_session.updated",
                    "session.created",
                    "transcription_session.created",
                }:
                    await self._state_queue.put(event)

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

                evt_type = evt.get("type", "")
                if evt_type == "conversation.item.input_audio_transcription.completed":
                    transcript = cast(str, evt.get("transcript", ""))
                    if transcript:
                        await self._output_queue.put({"type": "transcript", "text": transcript})
                        self._end_turn(transcript)
                        self._start_turn()
                else:
                    await self._output_queue.put(evt)
            except asyncio.TimeoutError:
                break
            except Exception as exc:
                await self._output_queue.put(ErrorSentinel(exc))
                raise
        await self._output_queue.put(SessionCompleteSentinel())

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
                #logger.debug("Realtime transcription websocket established")

                await asyncio.gather(
                    self._listener_task,
                    self._process_events_task,
                    self._stream_audio_task,
                )
        except Exception as exc:
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
        self._ws_connection_task = asyncio.create_task(self._handle_websocket_connection())
        return self._output_queue

    async def close(self) -> None:
        if self._ws_connection_task:
            self._ws_connection_task.cancel()
        if self._websocket:
            await self._websocket.close()

async def main():
    import dotenv
    dotenv.load_dotenv()
    # Example usage
    client = AsyncOpenAI()
    transcriber = OpenAIRealtimeTranscriber(client, "whisper-1", STTModelSettings())
    
    input_queue = asyncio


if __name__ == "__main__":
    asyncio.run(main())
