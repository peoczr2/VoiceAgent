from events import TTSEvent, MediaEvent
from typing import List

class TTSService:
    async def synthesize(self, text: str) -> List[MediaEvent]:
        # Placeholder for TTS logic
        return [MediaEvent(audio_chunk=b"...")]

    async def cancel(self):
        # Placeholder for cancellation logic
        pass
