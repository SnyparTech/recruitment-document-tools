"""
Windows-safe uvicorn launcher for the Playwright-based Resdex backend.

On Windows, asyncio defaults to SelectorEventLoop which cannot spawn subprocesses.
async_playwright needs to spawn Chrome as a subprocess → requires ProactorEventLoop.

We must set the policy HERE, before uvicorn calls asyncio.new_event_loop(),
because setting it inside main.py is too late (loop already running by then).

Usage:
    python run.py
    python run.py --port 8002
    python run.py --no-reload
"""
import asyncio
import sys

if sys.platform == "win32":
    # Must be set before uvicorn creates the event loop.
    # ProactorEventLoop is the only loop on Windows that supports subprocess spawning,
    # which async_playwright needs to launch the Chrome/Chromium browser process.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the profile-bot backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        loop="asyncio",   # Tells uvicorn to use asyncio (ProactorEventLoop via policy above)
        log_level="info",
    )
