import asyncio
import webview

class API:
    def __init__(self):
        self.selections = []

    async def on_selection(self, text: str):
        print(f"Selection: {text}")
        self.selections.append(text)

async def main():
    api = API()
    window = webview.create_window('VoiceAgent Browser', 'ui/index.html', js_api=api)
    await webview.start(http_server=True)

if __name__ == '__main__':
    asyncio.run(main())
