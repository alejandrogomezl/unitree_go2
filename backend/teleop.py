import asyncio
import pygame
from time import monotonic
from loguru import logger
from .settings import Settings

# Mapeo por defecto (igual que tu main.py):
AX_LX_DEFAULT = 0  # izquierda/derecha (lateral -> y)
AX_LY_DEFAULT = 1  # arriba/abajo (avance -> x, invertido)
AX_RX_DEFAULT = 2  # yaw (derecha -> +z)

def apply_deadzone(v: float, dz: float) -> float:
    return 0.0 if abs(v) < dz else v

class XboxTeleop:
    """
    Teleop Go2 con doble backend:
      - SDL2 GameController (pygame._sdl2.controller.Controller) si está disponible
      - Joystick clásico (pygame.joystick.Joystick) como fallback

    Controles:
      y <- LX
      x <- -LY
      z <- RX

    Botones (configurables en Settings):
      - btn_stand : StandUp
      - btn_sit   : Sit (o StandDown)
      - btn_stop  : StopMove
    """

    def __init__(self, client, settings: Settings):
        self.client = client
        self.settings = settings

        self._task: asyncio.Task | None = None
        self._running = False
        self._last_dump = 0.0

        # ---- Inicializa pygame ----
        pygame.init()
        pygame.joystick.init()

        # ---- Backend 1: SDL2 GameController ----
        self.gc = None
        try:
            from pygame._sdl2 import controller as sdl2c  # type: ignore
            if sdl2c.get_count() > 0:
                self.gc = sdl2c.Controller(0)
                logger.success(f"🎮 [SDL2] Controlador: {self.gc.name}")
        except Exception as e:
            if self.settings.log_gamepad:
                logger.debug(f"[SDL2] Controller no disponible: {e}")

        # ---- Backend 2: Joystick clásico ----
        self.js = None
        if pygame.joystick.get_count() > 0:
            self.js = pygame.joystick.Joystick(0)
            self.js.init()
            try:
                name = self.js.get_name()
            except Exception:
                name = "Unknown Controller"
            logger.success(f"🎮 [JOY ] Joystick: {name}")
            logger.info(f"[JOY ] Axes={self.js.get_numaxes()} Buttons={self.js.get_numbuttons()} Hats={self.js.get_numhats()}")
        elif not self.gc:
            logger.warning("⚠️ No se ha detectado ningún mando en SDL2 ni Joystick.")

        # Ejes (forzables desde settings)
        self.ax_lx = AX_LX_DEFAULT if self.settings.ls_x_axis is None else int(self.settings.ls_x_axis)
        self.ax_ly = AX_LY_DEFAULT if self.settings.ls_y_axis is None else int(self.settings.ls_y_axis)
        self.ax_rx = AX_RX_DEFAULT if self.settings.yaw_axis  is None else int(self.settings.yaw_axis)

        # Estado previo para logs de cambios
        self._prev_axes: dict[str, float] = {}
        self._prev_buttons: dict[int, bool] = {}

    # ---------- Utilidades de estado ----------

    def connected(self) -> bool:
        return bool(self.gc) or bool(self.js)

    def num_axes(self) -> int:
        if self.gc:
            return 6  # mapeo típico
        if self.js:
            return self.js.get_numaxes()
        return 0

    def num_buttons(self) -> int:
        if self.gc:
            return 16  # mapeo típico Xbox
        if self.js:
            return self.js.get_numbuttons()
        return 0

    def _axis_raw_gc(self, idx: int) -> float:
        """
        SDL2 GameController mapea por nombre:
          0: leftx, 1: lefty, 2: rightx, 3:righty, 4:lefttrigger, 5:righttrigger
        """
        try:
            v = 0.0
            if idx == 0:
                v = float(self.gc.get_axis(0))  # leftx
            elif idx == 1:
                v = float(self.gc.get_axis(1))  # lefty
            elif idx == 2:
                v = float(self.gc.get_axis(2))  # rightx
            elif idx == 3:
                v = float(self.gc.get_axis(3))  # righty
            elif idx == 4:
                v = float(self.gc.get_axis(4))  # lefttrigger
            elif idx == 5:
                v = float(self.gc.get_axis(5))  # righttrigger
            return v
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

    # ---------- Teleop ----------

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
        # Pausa breve para datachannel
        await asyncio.sleep(0.12)

        while self._running:
            try:
                # Pump de eventos siempre (importante en macOS)
                pygame.event.pump()

                # Lee eventos de botones (por si el backend joystick emite)
                for event in pygame.event.get():
                    if event.type == pygame.JOYBUTTONDOWN:
                        if self.settings.log_gamepad:
                            logger.debug(f"[BTN DOWN] {event.button}")
                        await self._handle_button_down(event.button)
                    elif event.type == pygame.JOYBUTTONUP:
                        if self.settings.log_gamepad:
                            logger.debug(f"[BTN UP] {event.button}")

                # Lee ejes crudos
                lx = self.axis_raw(self.ax_lx)
                ly = self.axis_raw(self.ax_ly)
                rx = self.axis_raw(self.ax_rx)

                # Dump periódico y on-change (sólo si está activado)
                if self.settings.log_gamepad:
                    now = monotonic()
                    if now - self._last_dump > 1.0:
                        self._last_dump = now
                        logger.debug(f"[axes raw] LX(a{self.ax_lx})={lx:+.2f}  LY(a{self.ax_ly})={ly:+.2f}  RX(a{self.ax_rx})={rx:+.2f}")

                    def log_change(key, cur, eps=0.04):
                        prev = self._prev_axes.get(key, 0.0)
                        if abs(cur - prev) >= eps:
                            logger.debug(f"[axis Δ] {key}: {prev:+.2f} → {cur:+.2f}")
                            self._prev_axes[key] = cur

                    log_change(f"a{self.ax_lx}", lx)
                    log_change(f"a{self.ax_ly}", ly)
                    log_change(f"a{self.ax_rx}", rx)

                # Deadzone y escalado (igual que tu script)
                dz = float(self.settings.deadzone)
                x = -apply_deadzone(ly, dz) * float(self.settings.max_speed)
                y =  apply_deadzone(lx, dz) * float(self.settings.max_speed)
                z =  apply_deadzone(rx, dz) * float(self.settings.max_yaw)

                # Inversiones
                if self.settings.invert_x: x = -x
                if self.settings.invert_y: y = -y
                if self.settings.invert_z: z = -z

                # Enviar al robot
                await self.client.send_move(x, y, z)

            except Exception as e:
                logger.warning(f"Teleop loop error: {e}")

            await asyncio.sleep(0.03)  # ~33 Hz

    # ---------- Acciones de botones (configurables) ----------
    async def _handle_button_down(self, btn: int):
        """
        Ejecuta la acción configurada en Settings.button_actions.
        Ejemplo:
            button_actions = {0: "StandUp", 1: "Sit", 2: "Hello"}
        """
        try:
            cmd_name = self.settings.button_actions.get(btn)
            if not cmd_name:
                if self.settings.log_gamepad:
                    logger.debug(f"Botón {btn} sin acción asignada.")
                return

            if self.settings.log_gamepad:
                logger.info(f"🎮 Botón {btn} → Ejecutando comando: {cmd_name}")

            # Llama a la API del cliente con el comando dinámico
            await self.client.cmd(cmd_name)

        except Exception as e:
            logger.warning(f"Acción de botón falló (btn={btn}): {e}")

