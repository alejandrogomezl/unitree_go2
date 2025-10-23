from typing import Dict, Tuple
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
    if platform.system() == "Darwin":
        # macOS -> autodetección completa
        ls_x_axis: int | None = None
        ls_y_axis: int | None = None
        yaw_axis: int | None = None
    else:
        # Linux / Raspberry -> yaw fijo en 3
        ls_x_axis: int | None = None
        ls_y_axis: int | None = None
        yaw_axis: int | None = 3

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
        1: "Hello",
        0: "FingerHeart",
        3: "Stretch",
        9: "Dance1",
        8: "StopMove",
        2: "FrontJump",
    }
    )
    
    hat_actions: Dict[Tuple[int, int], str] = {
        (1, 0): "Sit",
        (0, 1): "StandUp",
        (0, -1): "StandDown",
    }