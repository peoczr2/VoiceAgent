import asyncio
import websockets
import pyaudio
import wave
import os

# --------- CONFIGURATION ---------
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
WS_URI = "ws://localhost:8765"
AUDIO_FILE = "output.wav"

# --------- SERVER: RECEIVE AUDIO & SAVE ---------
class AudioReceiver:
    def __init__(self):
        self.frames = []

    async def handler(self, websocket):
        print("🟢 Server: Client connected.")
        try:
            async for message in websocket:
                self.frames.append(message)
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Server: Client disconnected.")
        finally:
            self.save_audio()

    def save_audio(self):
        print(f"💾 Saving audio to {AUDIO_FILE}...")
        with wave.open(AUDIO_FILE, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
        print("✅ File saved.")

async def start_server(receiver):
    return await websockets.serve(receiver.handler, "localhost", 8765)

# --------- CLIENT: MIC AUDIO TO WEBSOCKET ---------
async def audio_client():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)

    async with websockets.connect(WS_URI) as ws:
        print("🎙️ Client: Recording. Press Ctrl+C to stop.")
        try:
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                await ws.send(data)
        except KeyboardInterrupt:
            print("⏹️ Client: Stopping.")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

# --------- MAIN ---------
async def main():
    receiver = AudioReceiver()
    await start_server(receiver)
    await asyncio.sleep(0.5)  # Let server boot
    await audio_client()

asyncio.run(main())
