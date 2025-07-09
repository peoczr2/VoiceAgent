from events import AudioEvent, TranscriptEvent
from typing import AsyncIterator

class UserTranscriber:
    async def stream(self, media_event: AudioEvent) -> AsyncIterator[TranscriptEvent]:
        # Placeholder for actual transcription logic
        yield TranscriptEvent(text="...user speech...")
