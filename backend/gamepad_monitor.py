import asyncio
import pygame
from loguru import logger
from .logger import broadcast_gamepad

class GamepadMonitor:
    """
    Monitor global del estado del mando, independiente del robot.
    Funciona en tiempo real porque cada 'interval' re-inicializa SDL
    (quit/init) para forzar el re-escaneo de joysticks.
    """
    _instance = None

    def __new__(cls, interval: float = 1.0):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._interval = interval
            cls._instance._task = None
            cls._instance.connected = False
        return cls._instance

    async def start(self):
        if self._task:
            return
        # Inicializa pygame una vez
        pygame.init()
        self._task = asyncio.create_task(self._loop())
        logger.info("🕹️ GamepadMonitor iniciado.")

    async def _loop(self):
        while True:
            try:
                # Forzar reescaneo de dispositivos
                pygame.joystick.quit()
                pygame.joystick.init()
                count = pygame.joystick.get_count()
                new_state = count > 0

                if new_state != self.connected:
                    self.connected = new_state
                    if new_state:
                        # Si hay mando, coge el primero y anúncialo
                        js = pygame.joystick.Joystick(0)
                        js.init()
                        logger.success(f"🎮 Mando conectado: {js.get_name()}")
                    else:
                        logger.warning("⚠️ Mando desconectado.")

                    # Notifica al frontend en tiempo real
                    await broadcast_gamepad(self.connected)

            except Exception as e:
                logger.exception(f"Error en GamepadMonitor: {e}")

            await asyncio.sleep(self._interval)

    def status(self) -> bool:
        return self.connected
