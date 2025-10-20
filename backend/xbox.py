import pygame
import asyncio
from loguru import logger
from .logger import broadcast_gamepad

def deadzone(v, dz):
    return 0.0 if abs(v) < dz else v


class XboxReader:
    def __init__(self, dz, max_x, max_y, max_z):
        self.dz = dz
        self.max_x, self.max_y, self.max_z = max_x, max_y, max_z
        self.js = None

    def init(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            return False
        self.js = pygame.joystick.Joystick(0)
        self.js.init()
        logger.success(f"Mando detectado: {self.js.get_name()}")
        return True

    def is_connected(self):
        return pygame.joystick.get_count() > 0

    def read(self):
        if not self.js:
            raise RuntimeError("No hay mando inicializado.")
        buttons = {}
        for e in pygame.event.get():
            if e.type == pygame.JOYBUTTONDOWN:
                buttons[e.button] = True
        lx, ly, rx = self.js.get_axis(0), self.js.get_axis(1), self.js.get_axis(3)
        x = deadzone(-ly, self.dz) * self.max_x
        y = deadzone(lx, self.dz) * self.max_y
        z = deadzone(rx, self.dz) * self.max_z
        return x, y, z, buttons

    def close(self):
        try:
            pygame.quit()
        except Exception:
            pass


# === Monitor global de mando ===
class GamepadMonitor:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.connected = False
            cls._instance.task = None
        return cls._instance

    async def run(self):
        pygame.init()
        pygame.joystick.init()
        logger.info("🕹️ Monitor de mando iniciado.")
        while True:
            new_state = pygame.joystick.get_count() > 0
            if new_state != self.connected:
                self.connected = new_state
                if new_state:
                    logger.success("🎮 Mando conectado.")
                else:
                    logger.warning("⚠️ Mando desconectado.")
                # Notificar al frontend en tiempo real
                await broadcast_gamepad(new_state)
            await asyncio.sleep(1)

    async def start(self):
        if not self.task:
            self.task = asyncio.create_task(self.run())

    def status(self):
        return self.connected
