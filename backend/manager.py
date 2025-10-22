from dataclasses import dataclass
from typing import Optional, Dict, Any

from .go2_client import Go2Client
from .teleop import XboxTeleop
from .settings import Settings

@dataclass
class Status:
    running: bool
    gamepad_connected: bool
    config: dict

class TeleopManager:
    def __init__(self):
        self.settings = Settings()
        self.client = Go2Client()
        self.teleop = XboxTeleop(client=self.client, settings=self.settings)

    async def connect(self, method: Optional[str] = None, ip: Optional[str] = None):
        if method is None:
            method = self.settings.method
        if ip is None:
            ip = self.settings.ip
        await self.client.connect(method, ip)

    async def disconnect(self):
        await self.client.disconnect()

    async def start(self):
        await self.teleop.start()

    async def stop(self):
        await self.teleop.stop()

    def status(self) -> Status:
        return Status(
            running=self.teleop.is_running(),
            gamepad_connected=self.teleop.connected(),
            config=self.settings.model_dump(),
        )

    # ---- helpers para debug/config ----

    def gamepad_state(self) -> Dict[str, Any]:
        n_axes = self.teleop.num_axes()
        n_btns = max(12, self.teleop.num_buttons())
        axes = [self.teleop.axis_raw(i) for i in range(n_axes)]
        buttons = [self.teleop.button_state(i) for i in range(n_btns)]
        return {
            "connected": self.teleop.connected(),
            "axes": axes,
            "buttons": buttons,
        }

    def update_settings(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        # actualiza solo las claves conocidas
        for k, v in patch.items():
            if hasattr(self.settings, k):
                setattr(self.settings, k, v)
        # reconfigurar ejes si han cambiado
        if hasattr(self.teleop, "ax_lx"):
            self.teleop.ax_lx = self.settings.ls_x_axis if self.settings.ls_x_axis is not None else 0
        if hasattr(self.teleop, "ax_ly"):
            self.teleop.ax_ly = self.settings.ls_y_axis if self.settings.ls_y_axis is not None else 1
        if hasattr(self.teleop, "ax_rx"):
            self.teleop.ax_rx = self.settings.yaw_axis  if self.settings.yaw_axis  is not None else 3
        return self.settings.model_dump()
