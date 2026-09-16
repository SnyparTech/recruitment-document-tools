"""
Playwright Thread Bridge for Windows + uvicorn compatibility.

Root cause: uvicorn explicitly creates a _WindowsSelectorEventLoop on Windows,
which cannot spawn subprocesses (required by async_playwright to launch Chrome).
Setting asyncio.set_event_loop_policy() in main.py or run.py is too late --
the loop is already created before app code runs.

Solution: Run all Playwright operations on a dedicated daemon thread that has
its own asyncio.ProactorEventLoop. FastAPI awaits results via run_in_executor.

Tested locally:
  asyncio.run()           -> ProactorEventLoop  -> subprocess OK
  _WindowsSelectorEventLoop -> subprocess FAILS (NotImplementedError)
  This thread             -> ProactorEventLoop  -> subprocess OK  ✓
"""

import asyncio
import logging
import sys
import threading
from typing import Any, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _PlaywrightEventLoopThread(threading.Thread):
    """
    Daemon thread that owns a ProactorEventLoop and runs it forever.
    All Playwright coroutines are submitted to this loop via
    asyncio.run_coroutine_threadsafe(), bypassing uvicorn's SelectorEventLoop.
    """

    def __init__(self) -> None:
        super().__init__(name="PlaywrightLoop", daemon=True)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    def run(self) -> None:
        # ProactorEventLoop supports subprocess spawning on Windows.
        # On Linux/macOS the default new_event_loop() already works.
        if sys.platform == "win32":
            self._loop = asyncio.ProactorEventLoop()
        else:
            self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        logger.info(f"[PlaywrightThread] Started with {type(self._loop).__name__}")
        self._loop.run_forever()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        self._ready.wait(timeout=10)
        if self._loop is None:
            raise RuntimeError("Playwright event loop thread failed to start within 10s")
        return self._loop


# ── Module-level singleton ────────────────────────────────────────────────────

_playwright_thread: _PlaywrightEventLoopThread | None = None
_lock = threading.Lock()


def _get_thread() -> _PlaywrightEventLoopThread:
    global _playwright_thread
    if _playwright_thread is None or not _playwright_thread.is_alive():
        with _lock:
            if _playwright_thread is None or not _playwright_thread.is_alive():
                _playwright_thread = _PlaywrightEventLoopThread()
                _playwright_thread.start()
                _playwright_thread._ready.wait(timeout=10)
    return _playwright_thread


# ── Public API ────────────────────────────────────────────────────────────────

async def run_on_playwright_loop(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async Playwright coroutine on the dedicated ProactorEventLoop thread
    and await the result from FastAPI's SelectorEventLoop.

    Usage in naukri_resdex.py:
        result = await run_on_playwright_loop(self._execute_plan_async(plan))
    """
    playwright_loop = _get_thread().loop

    # Submit the coroutine to the Playwright loop (thread-safe)
    future = asyncio.run_coroutine_threadsafe(coro, playwright_loop)

    # Await without blocking FastAPI's event loop
    main_loop = asyncio.get_event_loop()
    return await main_loop.run_in_executor(None, future.result)
