from typing import Dict
from pydantic import BaseModel

class Settings(BaseModel):
    # Conexión
    method: str = "localsta"
    ip: str | None = None

    # Movimiento
    deadzone: float = 0.12
    max_speed: float = 0.9
    max_yaw: float = 2.8
    ls_x_axis: int | None = None
    ls_y_axis: int | None = None
    yaw_axis: int | None = None

    # Inversiones
    invert_x: bool = False
    invert_y: bool = True
    invert_z: bool = True

    log_gamepad: bool = False

    # Mapeo de botones
    button_actions: Dict[int, str] = {
        0: "StandUp",
        1: "Sit",
        2: "Hello",
        3: "FingerHeart",
        4: "Stretch",
        5: "Dance1",
        6: "StopMove"
    }

    # Mapeo de cruceta (botones en mac)
    dpad_map: Dict[str, int] = {"up": 14, "down": 15, "left": 16, "right": 17}

    # Acciones de cruceta
    dpad_actions: Dict[str, str] = {
        "up": "StandUp",
        "down": "Sit",
        "left": "Hello",
        "right": "FingerHeart",
    }
