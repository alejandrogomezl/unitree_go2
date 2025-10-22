
import asyncio
from loguru import logger

class GamepadMonitor:
    """Placeholder for future WS broadcast of gamepad state."""
    def __init__(self, manager):
        self.manager = manager
        self._task = None
        self._running = False

    async def start(self):
        if self._running: return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.debug("GamepadMonitor started.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try: 
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self):
        while self._running:
            # Could push updates via WS here if needed
            await asyncio.sleep(1.0)
