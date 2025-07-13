import asyncio
from thresh.media_control import MediaControl
from voice_pipeline import VoicePipeline
from user_transcriber import UserTranscriber
from agent_transcriber import AgentTranscriber
from agent_service import AgentService
from tts_service import TTSService
from events import BaseEvent, MediaEvent
from typing import AsyncIterator

class LocalMediaControl(MediaControl):
    async def get_event_stream(self) -> AsyncIterator[BaseEvent]:
        yield MediaEvent(audio_chunk=b'hello world')

    async def run(self, output_stream: AsyncIterator[BaseEvent]):
        async for event in output_stream:
            if isinstance(event, MediaEvent):
                print(f"Playing audio: {event.audio_chunk}")

async def main():
    media_control = LocalMediaControl()
    voice_pipeline = VoicePipeline(
        user_transcriber=UserTranscriber(),
        agent_service=AgentService(),
        tts_service=TTSService(),
        agent_transcriber=AgentTranscriber(),
    )

    input_stream = media_control.get_event_stream()
    output_stream = voice_pipeline.handle_input_events(input_stream)
    await media_control.run(output_stream)

if __name__ == "__main__":
    asyncio.run(main())
