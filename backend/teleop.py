import asyncio, time
from loguru import logger
from .go2_client import Go2Client
from .xbox import XboxReader
from .settings import settings

class Teleop:
    def __init__(self, method: str, ip: str | None):
        self.client = Go2Client(method, ip)
        self.reader = XboxReader(settings.deadzone, settings.max_x, settings.max_y, settings.max_z)
        self.running = False
        self.period = 1 / settings.rate_hz
        self.gamepad_connected = False

    async def start(self):
        self.gamepad_connected = self.reader.init()
        if not self.gamepad_connected:
            logger.warning("⚠️ No hay mando, pero se intentará iniciar igualmente.")
        await self.client.connect()
        await self.client.command("StandUp")
        self.running = True
        logger.info("Teleoperación iniciada.")

    async def stop(self):
        self.running = False
        try:
            await self.client.command("StopMove")
            await self.client.move(0,0,0)
        except Exception:
            pass
        await self.client.disconnect()
        self.reader.close()
        logger.info("Teleoperación detenida.")

    async def run(self):
        last = 0
        try:
            while self.running:
                # Si el mando se desconecta, avisamos
                if not self.reader.is_connected():
                    if self.gamepad_connected:
                        logger.warning("❌ Mando desconectado")
                    self.gamepad_connected = False
                    await asyncio.sleep(1)
                    continue
                else:
                    if not self.gamepad_connected:
                        logger.success("✅ Mando reconectado")
                    self.gamepad_connected = True

                # Leer mando
                x, y, z, btn = self.reader.read()
                if 0 in btn: await self.client.command("StandUp")
                if 1 in btn: await self.client.command("Sit")
                if 7 in btn: await self.client.command("StopMove")

                now = time.time()
                if now - last >= self.period:
                    await self.client.move(x, y, z)
                    last = now
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
