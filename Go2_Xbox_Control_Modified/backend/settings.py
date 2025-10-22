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

    # LOG de entrada del mando
    log_axes_every: float = 1.0   # dump completo de ejes cada N segundos
    log_on_change: bool = True    # log en cambios significativos
    change_eps: float = 0.06      # umbral de cambio para log de ejes
    log_max_changes_per_tick: int = 8  # límites por ciclo para no inundar logs
    log_raw_axes: bool = True     # loguear valores crudos (sin deadzone)
