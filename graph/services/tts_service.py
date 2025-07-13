from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import numpy.typing as npt
from openai import AsyncOpenAI

from .service import Service
from events import TTSEvent, AudioEvent, ErrorEvent


class TTSService(Service):
    """Abstract base class for text-to-speech services."""

    def __init__(self, name: str = "TTSService") -> None:
        super().__init__(name)

    async def synthesize(self, text: str) -> npt.NDArray[np.int16]:
        """Convert ``text`` to a PCM int16 numpy array."""
        raise NotImplementedError

    async def handle(self, publisher: str, event: Any) -> None:
        if isinstance(event, TTSEvent):
            try:
                audio = await self.synthesize(event.text)
                await self.publish(AudioEvent(data=audio))
            except Exception as exc:  # pragma: no cover - defensive
                await self.publish(ErrorEvent(error=str(exc)))
        # ignore unrelated events

    async def run(self) -> asyncio.Task:
        self.run_task = asyncio.create_task(self.start())
        return self.run_task


class OpenAITTSService(TTSService):
    """TTSService implementation using the OpenAI API."""

    def __init__(self, client: AsyncOpenAI, model: str = "tts-1", voice: str = "nova") -> None:
        super().__init__(name="OpenAITTSService")
        self._client = client
        self._model = model
        self._voice = voice

    async def synthesize(self, text: str) -> npt.NDArray[np.int16]:
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
