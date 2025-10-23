import asyncio
import pygame
from time import monotonic
from loguru import logger
from .settings import Settings

AX_LX_DEFAULT = 0  # izquierda/derecha (lateral -> y)
AX_LY_DEFAULT = 1  # arriba/abajo (avance -> x, invertido)
AX_RX_DEFAULT = 2  # yaw (derecha -> +z)

def apply_deadzone(v: float, dz: float) -> float:
    return 0.0 if abs(v) < dz else v


class XboxTeleop:
    """
    Teleop Go2 compatible con macOS, Linux y Raspberry Pi.
    - Lee mandos vía SDL2 o pygame.joystick
    - Detecta automáticamente la cruceta (botones o hat)
    - Usa mapeos configurables en Settings para botones y D-Pad
    """

    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_dump = 0.0

        pygame.init()
        pygame.joystick.init()

        self.gc = None
        try:
            from pygame._sdl2 import controller as sdl2c  # type: ignore
            if sdl2c.get_count() > 0:
                self.gc = sdl2c.Controller(0)
                logger.success(f"🎮 [SDL2] Controlador: {self.gc.name}")
        except Exception as e:
            if self.settings.log_gamepad:
                logger.debug(f"[SDL2] Controller no disponible: {e}")

        self.js = None
        if pygame.joystick.get_count() > 0:
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            try:
                name = self.js.get_name()
            except Exception:
                name = "Unknown Controller"
            logger.success(f"🎮 [JOY ] Joystick: {name}")
            logger.info(
                f"[JOY ] Axes={self.js.get_numaxes()} Buttons={self.js.get_numbuttons()} Hats={self.js.get_numhats()}"
            )
        elif not self.gc:
            logger.warning("⚠️ No se ha detectado ningún mando en SDL2 ni Joystick.")

        self.ax_lx = AX_LX_DEFAULT if self.settings.ls_x_axis is None else int(self.settings.ls_x_axis)
        self.ax_ly = AX_LY_DEFAULT if self.settings.ls_y_axis is None else int(self.settings.ls_y_axis)
        self.ax_rx = AX_RX_DEFAULT if self.settings.yaw_axis is None else int(self.settings.yaw_axis)

        self._prev_axes: dict[str, float] = {}
        self._prev_buttons: dict[int, bool] = {}

    # ---------- Utilidades de estado ----------

    def connected(self) -> bool:
        return bool(self.gc) or bool(self.js)

    def num_axes(self) -> int:
        if self.gc:
            return 6
        if self.js:
            return self.js.get_numaxes()
        return 0

    def num_buttons(self) -> int:
        if self.gc:
            return 16
        if self.js:
            return self.js.get_numbuttons()
        return 0

    def _axis_raw_gc(self, idx: int) -> float:
        try:
            return float(self.gc.get_axis(idx))
        except Exception:
            return 0.0

    def axis_raw(self, i: int) -> float:
        if self.gc:
            return self._axis_raw_gc(i)
        if self.js and 0 <= i < self.js.get_numaxes():
            return float(self.js.get_axis(i))
        return 0.0

    def button_state(self, i: int) -> bool:
        if self.gc:
            try:
                return bool(self.gc.get_button(i))
            except Exception:
                return False
        if self.js and 0 <= i < self.js.get_numbuttons():
            return bool(self.js.get_button(i))
        return False

    # ---------- D-PAD (cruceta) ----------

    def _read_dpad(self):
        """
        Devuelve un diccionario con el estado de la cruceta (funciona en mac y Raspberry).
        """
        state = {"up": False, "down": False, "left": False, "right": False}

        # Caso 1: HAT (Linux/Raspberry)
        if self.js and self.js.get_numhats() > 0:
            hat_x, hat_y = self.js.get_hat(0)
            state["up"] = hat_y > 0
            state["down"] = hat_y < 0
            state["left"] = hat_x < 0
            state["right"] = hat_x > 0
            return state

        # Caso 2: Botones (macOS)
        dpad_map = getattr(self.settings, "dpad_map", {"up": 14, "down": 15, "left": 16, "right": 17})
        for name, idx in dpad_map.items():
            if self.button_state(idx):
                state[name] = True
        return state

    async def _handle_dpad(self):
        """
        Ejecuta acciones asociadas a la cruceta (si están definidas en Settings.dpad_actions).
        """
        dpad = self._read_dpad()
        for direction, pressed in dpad.items():
            if not pressed:
                continue
            cmd_name = self.settings.dpad_actions.get(direction)
            if not cmd_name:
                continue
            if self.settings.log_gamepad:
                logger.info(f"🎮 D-Pad {direction} → {cmd_name}")
            await self.client.cmd(cmd_name)

    # ---------- Teleop principal ----------

    def is_running(self) -> bool:
        return self._running

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Teleoperación iniciada.")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        try:
            await self.client.estop_soft()
        except Exception:
            pass
        logger.info("Teleoperación detenida.")

    async def _loop(self):
        await asyncio.sleep(0.12)
        while self._running:
            try:
                pygame.event.pump()
                for event in pygame.event.get():
                    if event.type == pygame.JOYBUTTONDOWN:
                        if self.settings.log_gamepad:
                            logger.debug(f"[BTN DOWN] {event.button}")
                        await self._handle_button_down(event.button)

                lx = self.axis_raw(self.ax_lx)
                ly = self.axis_raw(self.ax_ly)
                rx = self.axis_raw(self.ax_rx)

                dz = float(self.settings.deadzone)
                x = -apply_deadzone(ly, dz) * float(self.settings.max_speed)
                y = apply_deadzone(lx, dz) * float(self.settings.max_speed)
                z = apply_deadzone(rx, dz) * float(self.settings.max_yaw)

                if self.settings.invert_x:
                    x = -x
                if self.settings.invert_y:
                    y = -y
                if self.settings.invert_z:
                    z = -z

                await self.client.send_move(x, y, z)
                await self._handle_dpad()

            except Exception as e:
                logger.warning(f"Teleop loop error: {e}")

            await asyncio.sleep(0.03)  # ~33 Hz

    # ---------- Acciones de botones (configurables) ----------
    async def _handle_button_down(self, btn: int):
        try:
            cmd_name = self.settings.button_actions.get(btn)
            if not cmd_name:
                if self.settings.log_gamepad:
                    logger.debug(f"Botón {btn} sin acción asignada.")
                return
            if self.settings.log_gamepad:
                logger.info(f"🎮 Botón {btn} → {cmd_name}")
            await self.client.cmd(cmd_name)
        except Exception as e:
            logger.warning(f"Acción de botón falló (btn={btn}): {e}")
