
import asyncio
from loguru import logger

# Simple WS broadcast for logs
_ws_clients = set()
_lock = asyncio.Lock()

def setup_logging():
    # Add a sink that echoes to stdout and schedules WS broadcast
    def sink(msg):
        text = msg if isinstance(msg, str) else msg.strip()
        # schedule broadcast without awaiting
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_broadcast("log", text))
        except RuntimeError:
            # no loop, ignore
            pass
        # always print to console too
        print(text)
    logger.remove()
    logger.add(lambda m: sink(m), format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

async def _broadcast(kind: str, text: str):
    if not _ws_clients:
        return
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)

async def add_ws(ws):
    async with _lock:
        _ws_clients.add(ws)

async def remove_ws(ws):
    async with _lock:
        _ws_clients.discard(ws)
