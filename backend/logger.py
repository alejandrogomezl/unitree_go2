from loguru import logger
import asyncio, json

_ws_clients = set()
_lock = asyncio.Lock()

def setup_logging():
    logger.remove()
    logger.add(lambda msg: asyncio.create_task(_broadcast("log", msg.strip())), level="INFO")
    logger.add(lambda m: print(m, end=""))

async def _broadcast(event_type: str, message: str):
    async with _lock:
        dead = []
        for ws in list(_ws_clients):
            try:
                await ws.send_text(json.dumps({"type": event_type, "data": message}))
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_clients.discard(ws)

async def broadcast_gamepad(connected: bool):
    await _broadcast("gamepad", "connected" if connected else "disconnected")

async def add_ws(ws):
    async with _lock:
        _ws_clients.add(ws)

async def remove_ws(ws):
    async with _lock:
        _ws_clients.discard(ws)
