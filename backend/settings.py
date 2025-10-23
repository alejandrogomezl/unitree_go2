from typing import Dict
from pydantic import BaseModel
import platform

class Settings(BaseModel):
    # Conexión
    method: str = "localsta"
    ip: str | None = None

    # Parámetros de movimiento
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

    # Logs del mando
    log_gamepad: bool = True

    # -------- Mapeo dinámico de botones --------
    # Clave: índice del botón | Valor: comando SPORT_CMD
    button_actions: Dict[int, str] = (
    {
        # macOS mappings
        11: "StandUp",
        13: "Sit",
        1: "Hello",
        0: "FingerHeart",
        3: "Stretch",
        9: "Dance1",
        8: "StopMove",
        2: "FrontJump",
        12: "StandDown",
    }
    if platform.system() == "Darwin"
    else {
        # Raspberry/Linux mappings (más estándar)
        0: "StandUp",
        1: "Sit",
        2: "Hello",
        3: "FingerHeart",
        4: "Stretch",
        5: "Dance1",
        6: "StopMove",
        7: "FrontJump",
        8: "StandDown",
    }
)