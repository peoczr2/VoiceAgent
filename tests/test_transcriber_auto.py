import asyncio
import wave
import re
import os
import shutil
import logging
from pathlib import Path

import numpy as np


from openai import AsyncOpenAI
from transcriber import OpenAIRealtimeTranscriber, SessionCompleteSentinel, configure_logging
from events import AudioEvent

async def test_transcriber_on_beautiful_day(tmp_path):
    """Feed a WAV file saying 'What a beautiful day.' and check transcript."""
    if "OPENAI_API_KEY" not in os.environ:
        print("OPENAI_API_KEY not configured")
        return
    wav_fixture = Path("tests/fixtures/beautiful_day.wav")
    wav_path = tmp_path / "beautiful_day.wav"
    shutil.copy(wav_fixture, wav_path)
    with wave.open(str(wav_path), 'rb') as wf:
        assert wf.getsampwidth() == 2
        assert wf.getnchannels() == 1
        assert wf.getframerate() in (16000, 48000, 22050)
        frames = wf.readframes(wf.getnframes())

    frames_np = np.frombuffer(frames, dtype=np.int16)
    input_q: asyncio.Queue[AudioEvent] = asyncio.Queue()
    trans = OpenAIRealtimeTranscriber(AsyncOpenAI(), model="whisper-1")
    configure_logging(level=logging.DEBUG)
    output_q = await trans.start_session(input_q)
    chunk_size = 1024
    for i in range(0, len(frames_np), chunk_size):
        chunk = frames_np[i:i+chunk_size]
        await input_q.put(AudioEvent(data=chunk))
    await input_q.put(AudioEvent(data=None))

    transcripts = []
    while True:
        msg = await output_q.get()
        if isinstance(msg, SessionCompleteSentinel):
            break
        transcripts.append(getattr(msg, "text", str(msg)))
    full_text = " ".join(transcripts).strip()
    norm = lambda s: re.sub(r"[^\w\s]", "", s.lower())
    assert norm(full_text) == norm("what a beautiful day")
    await trans.close()

async def _main():
    configure_logging()
    tmp_path = Path("tests/tmp")
    tmp_path.mkdir(exist_ok=True)
    await test_transcriber_on_beautiful_day(tmp_path)
    shutil.rmtree(tmp_path, ignore_errors=True)

# python -m tests.test_transcriber_auto
if __name__ == "__main__":
    asyncio.run(_main())
    
