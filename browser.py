import asyncio
import urllib.parse
import webview

class API:
    def __init__(self):
        self.selections = []

    async def on_selection(self, text: str):
        print(f"Selection: {text}")
        self.selections.append(text)

    async def popout_tab(self, url: str, title: str | None = None):
        """Create a new window showing ``url``."""
        target = f"ui/index.html?url={urllib.parse.quote_plus(url)}"
        webview.create_window(title or "Tab", target, js_api=API())
        return True

async def main():
    api = API()
    window = webview.create_window('VoiceAgent Browser', 'ui/index.html', js_api=api)
    await webview.start(http_server=True)

if __name__ == '__main__':
    asyncio.run(main())
