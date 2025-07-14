import asyncio
import webview
from urllib.parse import quote

class API:
    def __init__(self):
        self.selections = []

    async def on_selection(self, text: str):
        print(f"Selection: {text}")
        self.selections.append(text)

    async def popout_tab(self, url: str, title: str):
        """Open a new window showing the given URL."""
        encoded_url = quote(url, safe="")
        encoded_title = quote(title or "New Tab")
        webview.create_window(title or "New Tab", f"ui/index.html?url={encoded_url}&title={encoded_title}", js_api=self)
        return True

async def main():
    api = API()
    window = webview.create_window('VoiceAgent Browser', 'ui/index.html', js_api=api)
    await webview.start(http_server=True)

if __name__ == '__main__':
    asyncio.run(main())
