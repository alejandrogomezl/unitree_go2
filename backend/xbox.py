import pygame
from loguru import logger

class Xbox:
    """
    Wrapper pygame para leer ejes/botones.
    Proporciona lectura cruda (sin deadzone) y con deadzone.
    """

    def __init__(self, deadzone: float = 0.12):
        self.deadzone = deadzone
        self.joy = None

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() > 0:
            self.joy = pygame.joystick.Joystick(0)
            self.joy.init()
            try:
                name = self.joy.get_name()
            except Exception:
                name = "Unknown Controller"
            logger.success(f"🎮 Mando detectado: {name}")
            logger.info(
                f"Axes={self.joy.get_numaxes()} Buttons={self.joy.get_numbuttons()} Hats={self.joy.get_numhats()}"
            )
        else:
            logger.warning("⚠️ No se ha detectado ningún mando.")

    def refresh(self):
        pygame.event.pump()

    # ---------- Lecturas ----------

    def _apply_deadzone(self, v: float) -> float:
        return 0.0 if abs(v) < self.deadzone else v

    def axis_raw(self, i: int) -> float:
        """Valor crudo del eje (sin deadzone)."""
        if not self.joy:
            return 0.0
        if i < 0 or i >= self.joy.get_numaxes():
            return 0.0
        return float(self.joy.get_axis(i))

    def axis(self, i: int) -> float:
        """Valor con deadzone aplicada."""
        return self._apply_deadzone(self.axis_raw(i))

    def button(self, i: int) -> bool:
        if not self.joy:
            return False
        if i < 0 or i >= self.joy.get_numbuttons():
            return False
        return bool(self.joy.get_button(i))

    def connected(self) -> bool:
        return self.joy is not None

    def num_axes(self) -> int:
        return 0 if not self.joy else self.joy.get_numaxes()

    def num_buttons(self) -> int:
        return 0 if not self.joy else self.joy.get_numbuttons()

    # ---------- Autodetección ----------

    def autodetect_axis_from_candidates(self, candidates: list[int]) -> int | None:
        """
        Devuelve el índice del eje con mayor |valor| dentro de 'candidates'.
        Requiere movimiento real (>0.20) para confirmar.
        """
        if not self.connected():
            return None
        n = self.num_axes()
        cands = [i for i in candidates if 0 <= i < n]
        if not cands:
            return None
        vals = [(i, abs(self.axis_raw(i))) for i in cands]
        best_i, best_val = max(vals, key=lambda t: t[1])
        return best_i if best_val > 0.20 else None
