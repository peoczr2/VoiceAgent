import sys
from pathlib import Path
import asyncio
import numpy as np
import pytest

from openai import AsyncOpenAI

sys.path.append(str(Path(__file__).resolve().parents[1]))
from tts_service import OpenAITTSService


class DummyResp:
    def __init__(self, chunks):
        self._chunks = chunks

    async def iter_bytes(self):
        for ch in self._chunks:
            yield ch


def test_openai_tts_synthesize(monkeypatch):
    chunks = [b"\x01\x00\x02\x00"]

    async def fake_create(*args, **kwargs):
        return DummyResp(chunks)

    client = AsyncOpenAI(api_key="test")
    monkeypatch.setattr(client.audio.speech.with_streaming_response, "create", fake_create)

    svc = OpenAITTSService(client)
    audio = asyncio.run(svc.synthesize("hi"))
    assert isinstance(audio, np.ndarray)
    assert audio.dtype == np.int16
    assert audio.tolist() == [1, 2]
