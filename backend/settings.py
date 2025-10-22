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
    invert_z: bool = True

     # -------- Logs de mando --------
    log_gamepad: bool = False      # <--- NUEVO: desactiva todos los logs del mando si False

    # -------- Mapeo de BOTONES (configurable) --------
    # Índices según pygame/SDL para mandos tipo Xbox:
    #   A=0, B=1, X=2, Y=3, LB=4, RB=5, BACK=6, START=7, LS=8, RS=9...
    btn_stand: int = 11     # A por defecto → StandUp
    btn_sit: int = 13       # B por defecto → Sit / StandDown
    btn_stop: int = 8      # START por defecto → StopMove
    btn_standdown: int = 12 # Y por defecto → StandDown (nuevo botón añadido)
    btn_frontjump: int = 2  # X por defecto → FrontJump (nuevo botón añadido)
    btn_hello: int = 1      # RB por defecto → Greet (nuevo botón añadido)
    btn_fingerheart: int = 0       # LB por defecto → FingerHeart (nuevo botón añadido)
    btn_stretch: int = 3    # RS por defecto → Stretch (nuevo botón añadido)
    btn_dance1: int = 9     # BACK por defecto → Dance1 (nuevo botón añadido)
