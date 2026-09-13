"""Double-click entry point for the frozen app.

Starts the local server (preferring port 8765, falling back to any free port) and
opens the browser to the drop zone. This is the script PyInstaller freezes into
LedgerOCR.exe -- the user never types a port or URL.
"""
import sys

from server import serve


def main():
    try:
        serve(host="127.0.0.1", port=8765, open_browser=True)
    except OSError:
        # 8765 already in use (e.g. a second launch) -> grab any free port.
        serve(host="127.0.0.1", port=0, open_browser=True)


if __name__ == "__main__":
    main()
