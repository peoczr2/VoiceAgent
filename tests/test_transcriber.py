from transcriber import OpenAIRealtimeTranscriber, configure_logging
from computer_media import ComputerMediaControl

async def _main():
    configure_logging()
    computer = ComputerMediaControl()

    import dotenv
    dotenv.load_dotenv()
    aclient = AsyncOpenAI()
    trans = OpenAIRealtimeTranscriber(aclient, model="gpt-4o-mini")

    computer_task = asyncio.create_task(computer.run())
    output_queue = await trans.start_session(computer.get_input_queue())
    computer.set_output_queue(output_queue)
    await computer_task

# python -m tests.transcriber_test
if __name__ == "__main__":
    asyncio.run(_main())
