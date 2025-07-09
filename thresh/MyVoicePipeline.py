import os
import asyncio
import json
import ssl

import sounddevice as sd
import openai
import websockets

from dotenv import load_dotenv
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



class VoicePipeline:
    def __init__(self, input_audio_ws, transccription_ws, workflow, output_audio_ws):
        self.input_audio_ws = input_audio_ws
        self.output_audio_ws = output_audio_ws
        self._running = True

    


# ─────────────────────────────────────────────────────────────────────────────
# 1. Audio capture: yield PCM16 chunks from your mic
# ─────────────────────────────────────────────────────────────────────────────

class MicrophoneStreamer:
    def __init__(self, samplerate=16000, blocksize=1024):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self._queue = asyncio.Queue()
        self.loop = asyncio.get_running_loop()
        self._stream = sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype='int16',
            channels=1,
            callback=self._audio_callback,
        )

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        # indata is a Python buffer of int16 PCM samples :contentReference[oaicite:3]{index=3}
        self.loop.call_soon_threadsafe(self._queue.put_nowait, bytes(indata))

    async def audio_generator(self):
        self._stream.start()
        print("🎤 Microphone streaming started")
        try:
            while True:
                chunk = await self._queue.get()
                yield chunk
        finally:
            self._stream.stop()
            self._stream.close()

# ─────────────────────────────────────────────────────────────────────────────
# 2. Create & connect a Realtime transcription session
# ─────────────────────────────────────────────────────────────────────────────

async def run_realtime_transcription():
    # Initialize OpenAI client
    openai.api_key = os.getenv("OPENAI_API_KEY")

    """# Create an ephemeral realtime transcription session :contentReference[oaicite:4]{index=4}
    session = client.beta.realtime.transcription_sessions.create(
        input_audio_format="pcm16",
        input_audio_transcription={"model": "gpt-4o-mini-transcribe"},
    )"""

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?intent=transcription",
        additional_headers={
            "Authorization": f"Bearer {openai.api_key}",
            "OpenAI-Beta": "realtime=v1",
            "OpenAI-Log-Session": "1",
        },
    ) as ws:
        print("🟢 Connected to Realtime API")

        mic = MicrophoneStreamer(samplerate=16000, blocksize=1024)

        send_task = asyncio.create_task(_send_audio_loop(ws, mic.audio_generator()))
        receive_task = asyncio.create_task(_receive_events_loop(ws))

        done, pending = await asyncio.wait(
            [send_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            if task.exception():
                # Propagate exceptions from tasks
                raise task.exception()

        for task in pending:
            task.cancel()


async def _receive_events_loop(ws):
    """Handle incoming server events."""
    async for message in ws:
        event = json.loads(message)
        await handle_server_event(event)


async def _send_audio_loop(ws, audio_gen):
    # Streams raw PCM bytes to the "input_audio_buffer.commit" channel
    async for chunk in audio_gen:
        await ws.send(chunk)
        #print(f"📤 Sent audio chunk of size {len(chunk)} bytes")
    # Signal end of stream if needed
    await ws.send(json.dumps({"type": "stop"}))

# ─────────────────────────────────────────────────────────────────────────────
# 3. Server event handler
# ─────────────────────────────────────────────────────────────────────────────

async def handle_server_event(event: dict):
    etype = event.get("type")
    if etype == "speech_started":
        print("▶️ Speech started")
    elif etype == "speech_stopped":
        print("⏹️ Speech stopped")
    elif etype == "transcription":
        print(f"🔄 Partial transcript: {event.get('text')}")
    elif etype == "transcription_complete":
        print(f"✅ Final transcript: {event.get('text')}")
    else:
        # Catch-all for any other server event types :contentReference[oaicite:6]{index=6}
        print(f"📡 Server event: {event}")

if __name__ == "__main__":
    try:
        asyncio.run(run_realtime_transcription())
    except KeyboardInterrupt:
        print("Exiting...")

