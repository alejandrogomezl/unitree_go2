from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from .logger import setup_logging, add_ws, remove_ws
from .manager import TeleopManager
from .gamepad_monitor import GamepadMonitor

app = FastAPI(title="Go2 Xbox Control")
setup_logging()
manager = TeleopManager()

# sirve frontend
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
