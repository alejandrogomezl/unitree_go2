# backend/server.py
import asyncio
from pathlib import Path
from typing import Any, Dict

# Fuerza el bucle estándar (mejora la estabilidad con aiortc/WebRTC frente a uvloop)
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass

from fastapi import FastAPI, WebSocket, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from loguru import logger

from .logger import setup_logging, add_ws, remove_ws
from .manager import TeleopManager
from .gamepad_monitor import GamepadMonitor

app = FastAPI(title="Go2 Xbox Control")
setup_logging()

manager = TeleopManager()
monitor = GamepadMonitor(manager)

# Rutas absolutas para el frontend
BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "frontend"
INDEX_HTML = STATIC_DIR / "index.html"

# Sirve frontend
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup_event():
    await monitor.start()
    logger.info("GamepadMonitor arrancado en el loop de FastAPI.")


@app.on_event("shutdown")
async def shutdown_event():
    # Detener teleoperación y desconectar del robot de forma ordenada
    try:
        await manager.stop()
    except Exception:
        pass
    try:
        await manager.disconnect()
    except Exception:
        pass
    try:
        await monitor.stop()
    except Exception:
        pass
    logger.info("Shutdown completo.")


# ---------- Modelos ----------

class ConnectBody(BaseModel):
    method: str
    ip: str | None = None

class MoveBody(BaseModel):
    x: float
    y: float
    z: float

class YawBody(BaseModel):
    wz: float


# ---------- Rutas API ----------

@app.get("/")
async def index():
    return FileResponse(str(INDEX_HTML))


@app.get("/api/status")
async def api_status():
    s = manager.status()
    return JSONResponse({
        "running": s.running,
        "gamepad_connected": s.gamepad_connected,
        "config": s.config,
    })


@app.post("/api/connect")
async def api_connect(body: ConnectBody):
    await manager.connect(body.method, body.ip)
    # AUTOSTART teleop para evitar que se quede parado si no se pulsa "Start Teleop"
    try:
        await manager.start()
        logger.info("Teleop auto-iniciada tras la conexión.")
    except Exception as e:
        logger.warning(f"No se pudo autoiniciar teleop: {e}")
    return JSONResponse({"ok": True})



@app.post("/api/disconnect")
async def api_disconnect():
    await manager.disconnect()
    return JSONResponse({"ok": True})


@app.post("/api/teleop/start")
async def api_start():
    await manager.start()
    return JSONResponse({"ok": True})


@app.post("/api/teleop/stop")
async def api_stop():
    await manager.stop()
    return JSONResponse({"ok": True})


@app.post("/api/stand")
async def api_stand():
    await manager.client.stand()
    return JSONResponse({"ok": True})


@app.post("/api/sit")
async def api_sit():
    await manager.client.sit()
    return JSONResponse({"ok": True})


@app.post("/api/stop")
async def api_stop_move():
    await manager.client.estop_soft()
    return JSONResponse({"ok": True})


@app.post("/api/move")
async def api_move(body: MoveBody):
    await manager.client.send_move(body.x, body.y, body.z)
    return JSONResponse({"ok": True})


@app.post("/api/yaw")
async def api_yaw(body: YawBody):
    # yaw-only convenience
    await manager.client.send_move(0.0, 0.0, body.wz)
    return JSONResponse({"ok": True})


# ---------- Endpoints de debug / configuración ----------

@app.get("/api/gamepad/state")
async def api_gamepad_state():
    """Devuelve ejes/botones y el índice autodetectado para RS-X."""
    return JSONResponse(manager.gamepad_state())


@app.post("/api/settings")
async def api_update_settings(patch: Dict[str, Any] = Body(...)):
    """
    Actualiza parte de la configuración en caliente.
    Ejemplo body:
    {
      "yaw_axis": 3,           // fuerza RS-X a axis(3) (None=autodetect)
      "invert_x": false,
      "invert_y": false,
      "invert_z": false,
      "deadzone": 0.12,
      "max_speed": 0.8,
      "max_yaw": 2.5
    }
    """
    cfg = manager.update_settings(patch)
    return JSONResponse({"ok": True, "settings": cfg})


@app.post("/api/test/move")
async def api_test_move(body: Dict[str, Any] = Body(...)):
    """
    Realiza un movimiento puntual para verificar que el robot obedece.
    Body: {"x":0.4,"y":0.0,"z":0.0,"duration_ms":600}
    """
    x = float(body.get("x", 0.0))
    y = float(body.get("y", 0.0))
    z = float(body.get("z", 0.0))
    duration_ms = int(body.get("duration_ms", 500))

    await manager.client.send_move(x, y, z)
    await asyncio.sleep(max(0, duration_ms) / 1000.0)
    await manager.client.estop_soft()
    return JSONResponse({"ok": True})


# ---------- WebSocket de logs ----------

@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    await add_ws(ws)
    logger.info("Cliente WS conectado.")
    try:
        while True:
            # keepalive
            await ws.receive_text()
    except Exception:
        pass
    finally:
        await remove_ws(ws)
        logger.info("Cliente WS desconectado.")
