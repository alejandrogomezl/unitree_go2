from pydantic import BaseModel

class Settings(BaseModel):
    # Conexión
    method: str = "localsta"      # "localsta" | "localap" | "remote"
    ip: str | None = None

    # Ganancias / deadzone
    deadzone: float = 0.12
    max_speed: float = 0.9        # escala x/y
    max_yaw: float = 2.8          # escala z (rad/s)

    # Mapeo de ejes (None => auto)
    ls_x_axis: int | None = None  # por defecto 0 si None
    ls_y_axis: int | None = None  # por defecto 1 si None
    yaw_axis:  int | None = None  # si None, autodetect

    # Inversiones
    invert_x: bool = False
    invert_y: bool = True
    invert_z: bool = False

     # -------- Logs de mando --------
    log_gamepad: bool = False      # <--- NUEVO: desactiva todos los logs del mando si False
