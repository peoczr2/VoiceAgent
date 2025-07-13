import asyncio

from graph.services.service import Service
from events import *
from graph.services.computer_media import ComputerMediaControl

EVENT_INACTIVITY_TIMEOUT = 1000

class EchoService(Service):
    """
    A simple Service that echoes audio events.
    """

    def __init__(self):
        pass

    async def handle(self, publisher: str, event: AudioEvent):
        if isinstance(event, AudioEvent):
            await self.output_queue.put(event)
        elif isinstance(event, ControlEvent) and event.type == 'end_session':
            print("Ending session as requested.")
            return

    async def run(self):
        asyncio.create_task








class EchoPipeline2:
    """
    A simple VoicePipeline that echoes back audio events.
    """

    def __init__(self):
        self.input_queue: asyncio.Queue[AudioEvent] | None = None
        self.output_queue: asyncio.Queue[AudioEvent] = asyncio.Queue()

    async def process_input(self) -> None:
        print("Starting input processing...")
        assert self.input_queue is not None, "Input queue must be set before processing input."
        while True:
            try:
                event = await asyncio.wait_for(
                    self.input_queue.get(), timeout=EVENT_INACTIVITY_TIMEOUT
                )
                match event:
                    case AudioEvent():
                        await self.output_queue.put(event)
                    case ControlEvent(type = 'end_session'):
                        break
                    
                    
                await asyncio.sleep(0)  # yield control
            except asyncio.TimeoutError:
                print("No new events for a while. Ending input processing.")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                break
        print("Input processing completed.")

    async def run(self, input_queue: asyncio.Queue[AudioEvent]) -> asyncio.Queue[AudioEvent]:
        print("Starting EchoPipeline...")
        self.input_queue = input_queue
        self.input_task = asyncio.create_task(self.process_input())
        print("EchoPipeline task started.")
        return self.output_queue
    
async def _main():
    computer = ComputerMediaControl()
    pipeline = EchoPipeline()

    computer_task = asyncio.create_task(computer.run())
    output_queue = await pipeline.run(computer.get_input_queue())
    computer.set_output_queue(output_queue)
    await computer_task
    

#python -m tests.computer_media_test
if __name__ == "__main__":
    asyncio.run(_main())