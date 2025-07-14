import os
import urllib.parse
import webview

ROOT = os.path.dirname(os.path.abspath(__file__))

class API:
    def __init__(self):
        self.selections: list[str] = []

    async def on_selection(self, text: str) -> None:
        """Called from JS when text is highlighted."""
        print(f"Selection: {text}")
        self.selections.append(text)

    async def popout_tab(self, url: str, title: str | None = None) -> bool:
        """Create a new window showing ``url``."""
        target = os.path.join(ROOT, "ui", "index.html") + f"?url={urllib.parse.quote_plus(url)}"
        webview.create_window(title or "Tab", target, js_api=API())
        return True

def main() -> None:
    api = API()
    index = os.path.join(ROOT, 'ui', 'index.html')
    webview.create_window('VoiceAgent Browser', index, js_api=api)
    webview.start(http_server=True)

if __name__ == '__main__':
    main()
