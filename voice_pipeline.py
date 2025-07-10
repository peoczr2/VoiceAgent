from media_control import MediaControl
from user_transcriber import UserTranscriber
from agent_service import AgentService
from tts_service import TTSService
from transcriber import AgentTranscriber
from events import *
from typing import AsyncIterator
import asyncio

EVENT_INACTIVITY_TIMEOUT = 1000



class VoicePipeline:
    def __init__(
        self,
        user_transcriber: UserTranscriber,
        agent_service: AgentService,
        tts_service: TTSService,
        agent_transcriber: AgentTranscriber,
    ):
        self.user_transcriber = user_transcriber
        self.agent_service = agent_service
        self.tts_service = tts_service
        self.agent_transcriber = agent_transcriber

        self.input_queue: asyncio.Queue[VoicePipelineInputEvent] | None = None
        self.user_audio_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self.user_transcribed_queue: asyncio.Queue[TranscriptEvent] = asyncio.Queue()
        self.agent_input_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self.agent_response_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self.tts_input_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self.tts_output_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self.output_queue: asyncio.Queue[BaseEvent] = asyncio.Queue()

        self.input_task: asyncio.Task = None
        self.user_transcribtion_task: asyncio.Task = None
        self.agent_response_task: asyncio.Task = None
        self.tts_task: asyncio.Task = None

    async def process_input(self) -> None:
        """
        Entry point for processing input events to the pipeline:
        - MediaEvent -> user_audio_queue
        - ControlEvent -> session/error handling
        """
        while True:
            try:
                event = await asyncio.wait_for(
                    self.input_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )
                match event:
                    case MediaEvent():
                        await self.user_audio_queue.put(event)
                    
                    
                await asyncio.sleep(0)  # yield control
            except asyncio.TimeoutError:
                # No new events for a while. Assume the session is done.
                break
            except Exception as e:
                await self._output_queue.put(ErrorEvent(error=str(e)))
                raise e
        await self._output_queue.put(SessionCompleteSentinel())

    async def process_user_transcription(self) -> None:
        """
        Processes transcription events from UserTranscriber:
        - handle events: speech_started, speech_stopped, transcription_completed
        """
        while True:
            try:
                event = await asyncio.wait_for(
                    self.user_transcribed_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )
                match event:
                    case TranscriptEvent(type = 'transcription_completed', text = text):
                        await self.agent_input_queue.put(event)
                    
                await asyncio.sleep(0)  # yield control
            except asyncio.TimeoutError:
                # No new events for a while. Assume the session is done.
                break
            except Exception as e:
                await self._output_queue.put(ErrorEvent(error=str(e)))
                raise e
        await self._output_queue.put(SessionCompleteSentinel())

    async def process_agent_response(self) -> None:
        """
        Streams generated text from AgentService to TTS.
        """
        while True:
            try:
                event = await asyncio.wait_for(
                    self.agent_response_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )
                match event:
                    case TranscriptionCompleted(text):
                        await self.tts_input_queue.put(text)
                    
                await asyncio.sleep(0)  # yield control
            except asyncio.TimeoutError:
                # No new events for a while. Assume the session is done.
                break
            except Exception as e:
                await self._output_queue.put(ErrorEvent(error=str(e)))
                raise e
        await self._output_queue.put(SessionCompleteSentinel())
    async def process_tts(self, tts_event: TTSEvent) -> AsyncIterator[BaseEvent]:
        """
        Converts text-to-speech events:
        - send audio to output_queue
        - optionally transcribe agent audio for context
        """
        while True:
            try:
                event = await asyncio.wait_for(
                    self.tts_output_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )
                match event:
                    case TranscriptionCompleted(text):
                        await self.output_queue.put(text)
                    
                await asyncio.sleep(0)  # yield control
            except asyncio.TimeoutError:
                # No new events for a while. Assume the session is done.
                break
            except Exception as e:
                await self._output_queue.put(ErrorEvent(error=str(e)))
                raise e
        await self._output_queue.put(SessionCompleteSentinel())

    async def start_session(self):
        print("Session started")

    async def end_session(self):
        print("Session ended")

    async def handle_error(self, data):
        print(f"An error occurred: {data}")

    async def run(self, input_queue: asyncio.Queue[MediaEvent]) -> asyncio.Queue[BaseEvent]:
        self.user_transcriber.start_session()
        self.agent_service.start_session()
        self.tts_service.start_session()
        self.agent_transcriber.start_session()

        self.input_task = asyncio.create_task(self.process_input_stream())

        return self.output_queue