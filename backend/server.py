# backend/server.py
import asyncio
from pathlib import Path
from typing import Any, Dict

# Fuerza el bucle estándar
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass

from fastapi import FastAPI, WebSocket, Body, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse
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
    # AUTOSTART teleop tras conexión
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
    await manager.client.send_move(0.0, 0.0, body.wz)
    return JSONResponse({"ok": True})


# ---------- Debug / Config ----------

@app.get("/api/gamepad/state")
async def api_gamepad_state():
    return JSONResponse(manager.gamepad_state())


@app.post("/api/settings")
async def api_update_settings(patch: Dict[str, Any] = Body(...)):
    cfg = manager.update_settings(patch)
    return JSONResponse({"ok": True, "settings": cfg})


@app.post("/api/test/move")
async def api_test_move(body: Dict[str, Any] = Body(...)):
    x = float(body.get("x", 0.0))
    y = float(body.get("y", 0.0))
    z = float(body.get("z", 0.0))
    duration_ms = int(body.get("duration_ms", 500))
    await manager.client.send_move(x, y, z)
    await asyncio.sleep(max(0, duration_ms) / 1000.0)
    await manager.client.estop_soft()
    return JSONResponse({"ok": True})


# ---------- Vídeo ----------

@app.get("/api/video/frame")
async def api_video_frame():
    """
    Último frame como image/jpeg (204 si aún no hay frame)
    """
    data = await manager.client.get_latest_jpeg()
    if not data:
        return Response(status_code=204)
    return Response(content=data, media_type="image/jpeg")


@app.get("/api/video/mjpeg")
async def api_video_mjpeg():
    """
    Stream MJPEG (multipart/x-mixed-replace)
    """
    boundary = "frame"

    async def gen():
        while True:
            data = await manager.client.wait_for_frame(timeout=2.0)
            if not data:
                # keep-alive para que el <img> no “muera”
                yield b"--" + boundary.encode() + b"\r\n\r\n"
                continue
            yield (
                b"--" + boundary.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(data)).encode() + b"\r\n\r\n" +
                data + b"\r\n"
            )

    return StreamingResponse(gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}")


# ---------- WebSocket de logs ----------

@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    await add_ws(ws)
    logger.info("Cliente WS conectado.")
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        await remove_ws(ws)
        logger.info("Cliente WS desconectado.")

class CmdBody(BaseModel):
    cmd: str

@app.post("/api/cmd")
async def send_cmd(body: CmdBody):
    """Execute a SPORT_CMD action manually from the web interface"""
    cmd_name = body.cmd
    try:
        await manager.client.cmd(cmd_name)
        logger.info(f"Executed manual command: {cmd_name}")
        return {"ok": True, "cmd": cmd_name}
    except Exception as e:
        logger.exception(f"Error executing command {cmd_name}: {e}")