import asyncio
from loguru import logger
from .teleop import Teleop
from .gamepad_monitor import GamepadMonitor

class TeleopManager:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._lock = asyncio.Lock()
            cls._instance._task = None
            cls._instance._teleop = None
            cls._instance._config = {}
            cls._instance._monitor = GamepadMonitor()
        return cls._instance

    async def connect(self, method: str, ip: str | None):
        async with self._lock:
            if self._task and not self._task.done():
                logger.info("Ya hay teleop en ejecución.")
                return {"running": True, "config": self._config, "gamepad_connected": self._monitor.status()}
            self._teleop = Teleop(method, ip)
            await self._teleop.start()
            self._config = {"method": method, "ip": ip}
            self._task = asyncio.create_task(self._teleop.run())
            return {"running": True, "config": self._config, "gamepad_connected": self._monitor.status()}

    async def disconnect(self):
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try: await self._task
                except Exception: pass
            self._task = None
            self._teleop = None
            logger.info("Teleop detenida.")
            return {"running": False, "gamepad_connected": self._monitor.status()}

    async def status(self):
        running = self._task and not self._task.done()
        return {
            "running": bool(running),
            "config": self._config if running else None,
            "gamepad_connected": self._monitor.status(),
        }
