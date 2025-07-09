## Voice Pipeline Architecture

This document outlines the refined architecture for a modular, Python-based voice agent pipeline. The central orchestrator (`VoicePipeline`) connects voice-processing components and handles event streams. A separate **Media Control** module provides and consumes event streams for local testing or production, without embedding hardware I/O into the core logic.

---

### High-Level Diagram

```text
+------------------------------------------------------------------+
|                           VoicePipeline                         |
|  +-------------+   +------------------+   +--------------+       |
|  | Transcribers |-->|    AgentService  |-->|   TTSService |       |
|  +-------------+   +------------------+   +--------------+       |
|          ^                   |                     |             |
|          |                   v                     v             |
|  [subscribe]    enqueue TTSEvent    emit MediaEvent             |
|          |                                                   |   |
|  +---------------------------------------------------------+  |   |
|  |                    Media Control                        |  |   |
|  |  - input_stream: AsyncIterator[RawEvent]                |  |   |
|  |  - output_sink: Callable[[MediaEvent], Awaitable[None]] |  |   |
|  +---------------------------------------------------------+  |   |
+------------------------------------------------------------------+
```

---

## Core Components

### 1. Media Control (`media_control.py`)

**Role:** Abstraction layer for diverse external media sources and sinks (e.g., Twilio, local microphone/speaker, test harness), decoupling hardware and service integrations from the core pipeline.

**Interface:**

````python
from typing import AsyncIterator, Awaitable, Callable

class MediaControl:
    def __init__(
        self,
        event_source: AsyncIterator[str],                   # Raw JSON payloads or binary frames from external sources
        event_sink: Callable[['MediaEvent'], Awaitable[None]]  # Async handler to push MediaEvents out to external sinks
    ):
        self.event_source = event_source
        self.event_sink = event_sink

    def get_event_stream(self) -> AsyncIterator['BaseEvent']:
        """
        Async iterator over parsed events for VoicePipeline.
        """
        async for raw in self.event_source:
            yield EventFactory.from_raw(raw)

    async def send_event(self, event: 'MediaEvent') -> None:
        """
        Push MediaEvent out to the external sink (e.g., speaker playback, Twilio call).
        """
        await self.event_sink(event)
```  ### 2. Orchestrator: `VoicePipeline` (`voice_pipeline.py`)

**Role:** Central manager of the voice pipeline, agnostic of hardware I/O, with dedicated handlers for each event flow.

**Construction & Wiring:**
```python
class VoicePipeline:
    def __init__(
        self,
        media_control: MediaControl,
        user_transcriber: UserTranscriber,
        agent_service: AgentService,
        tts_service: TTSService,
        agent_transcriber: AgentTranscriber,
    ):
        self.media_control = media_control
        self.user_transcriber = user_transcriber
        self.agent_service = agent_service
        self.tts_service = tts_service
        self.agent_transcriber = agent_transcriber

    async def start(self):
        async for event in self.media_control.get_event_stream():
            await self.input_event_handler(event)

    async def input_event_handler(self, event: BaseEvent):
        """
        Routes raw events:
        - MediaEvent -> user_transcriber
        - ControlEvent -> session/error handling
        """
        match event:
            case MediaEvent():
                await self.user_transcription_event_handler(event)
            case ControlEvent(type="start_session"):
                await self.start_session()
            case ControlEvent(type="end_session"):
                await self.end_session()
            case ControlEvent(type="error"):
                await self.handle_error(event.data)

    async def user_transcription_event_handler(self, media_event: MediaEvent):
        """
        Processes transcription workflow:
        - send to UserTranscriber
        - handle events: speech_started, speech_stopped, transcription_completed
        """
        async for evt in self.user_transcriber.stream(media_event):
            match evt.type:
                case 'speech_started':
                    # cancel any ongoing TTS
                    await self.tts_service.cancel()
                case 'speech_stopped':
                    # optional VAD end event handling
                    pass
                case 'transcription_completed':
                    # forward text to agent
                    await self.agent_service_event_handler(evt)

    async def agent_service_event_handler(self, transcript_event: TranscriptEvent):
        """
        Streams generated text from AgentService to TTS.
        """
        async for tts_evt in self.agent_service.generate(transcript_event.text):
            await self.tts_service_event_handler(tts_evt)

    async def tts_service_event_handler(self, tts_event: TTSEvent):
        """
        Converts text-to-speech events:
        - send audio to MediaControl
        - optionally transcribe agent audio for context
        """
        # produce MediaEvent audio via TTSService
        media_events = await self.tts_service.synthesize(tts_event.text)
        for media_evt in media_events:
            # playback or send over Twilio etc.
            await self.media_control.send_event(media_evt)
            # capture for context
            await self.agent_transcriber.transcribe(media_evt)
````

### 3. Transcribers Transcribers

#### a. `UserTranscriber` (`user_transcriber.py`)

- Converts `MediaEvent` (user audio) to `TranscriptEvent` via an external ASR service.

#### b. `AgentTranscriber` (`agent_transcriber.py`)

- Optionally transcribes TTS output for context continuity.

### 4. Agent Logic: `AgentService` (`agent_service.py`)

- Receives transcripts, applies dialogue logic, emits `TTSEvent`.

### 5. Text-to-Speech: `TTSService` (`tts_service.py`)

- Consumes `TTSEvent`, generates audio, issues `MediaEvent` both to playback (`output_sink`) and back to `AgentTranscriber`.

---

## Event Types

```python
class MediaEvent(BaseEvent):
    audio_chunk: bytes

class ControlEvent(BaseEvent):
    type: Literal['start_session','end_session','error']
    data: Optional[Any]

class TranscriptEvent(BaseEvent):
    text: str

class TTSEvent(BaseEvent):
    text: str
```

---

## Project Structure

```
.
├── ARCHITECTURE.md        # Updated architecture with Media Control
├── media_control.py       # Async input/output interface for events
├── voice_pipeline.py      # Core orchestrator with dependency injection
├── user_transcriber.py    # Transcribes user speech
├── agent_transcriber.py   # Transcribes agent speech for context
├── agent_service.py       # Decision logic and queuing
├── tts_service.py         # Text-to-speech conversion
├── main.py                # Wires up MediaControl and VoicePipeline
└── requirements.txt       # Python dependencies
```

