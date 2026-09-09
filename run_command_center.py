from __future__ import annotations
import argparse
import uvicorn
from command_center.app import app
def main() -> int:
    p=argparse.ArgumentParser(description="Run the Model Lab local command center")
    p.add_argument("--no-browser", action="store_true")
    p.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=8000)
    return 0
if __name__ == "__main__": raise SystemExit(main())
