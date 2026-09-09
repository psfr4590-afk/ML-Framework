from __future__ import annotations

import argparse
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from command_center.app import app


def main() -> int:
    p = argparse.ArgumentParser(description="Run the Model Lab local command center")
    p.add_argument("--no-browser", action="store_true", help="do not open the localhost command center in a browser")
    args = p.parse_args()

    if not args.no_browser:
        def _open_browser() -> None:
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8000/api/system", timeout=0.5):
                        webbrowser.open("http://127.0.0.1:8000")
                        return
                except Exception:
                    time.sleep(0.25)

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
