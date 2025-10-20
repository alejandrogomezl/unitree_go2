from pydantic import BaseModel

class Settings(BaseModel):
    rate_hz: float = 50.0
    deadzone: float = 0.08
    max_x: float = 0.7
    max_y: float = 0.5
    max_z: float = 1.5
    default_method: str = "localsta"

settings = Settings()
