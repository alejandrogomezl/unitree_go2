from __future__ import annotations

import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse
from loguru import logger

from .logger import setup_logging, add_ws, remove_ws
from .manager import TeleopManager
from .gamepad_monitor import GamepadMonitor
from .video import VIDEO_BUFFER  # <- buffer global de vídeo (placeholder+último frame)

app = FastAPI(title="Go2 Xbox Control")
setup_logging()
manager = TeleopManager()


app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.on_event("startup")
async def startup_event():
    # MUY IMPORTANTE: arrancar el monitor dentro del MISMO loop de FastAPI
    await GamepadMonitor().start()
    logger.info("GamepadMonitor arrancado en el loop de FastAPI.")

@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

@app.get("/api/status")
async def status():
    return await manager.status()

@app.post("/api/connect")
async def connect(req: dict):
    method = req.get("method", "localsta")
    ip = req.get("ip")
    res = await manager.connect(method, ip)
    return JSONResponse(res)

@app.post("/api/disconnect")
async def disconnect():
    res = await manager.disconnect()
    return JSONResponse(res)

@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    await add_ws(ws)
    logger.info("Cliente WS conectado.")
    try:
        while True:
            # Mantén el WS vivo; no esperamos mensajes del cliente
            await ws.receive_text()
    except Exception:
        pass
    finally:
        await remove_ws(ws)
        logger.info("Cliente WS desconectado.")

@app.get("/api/video.mjpg")
async def mjpeg():
    """
    Devuelve un stream MJPEG (multipart/x-mixed-replace) con el último frame.
    Si no hay vídeo del robot, se sirve un placeholder (negro con texto).
    """
    boundary = "frame"

    async def gen():
        while True:
            jpg = VIDEO_BUFFER.get_jpeg(quality=80)
            yield (
                b"--" + boundary.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" +
                jpg + b"\r\n"
            )
            # ~30-33 FPS. Ajusta si quieres menos consumo.
            await asyncio.sleep(0.03)

    headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}
    return StreamingResponse(gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}", headers=headers)
