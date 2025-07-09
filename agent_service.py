from events import TTSEvent, TranscriptEvent
from typing import AsyncIterator

class AgentService:
    async def generate(self, text: str) -> AsyncIterator[TTSEvent]:
        # Placeholder for agent logic
        yield TTSEvent(text=f"Echo: {text}")
