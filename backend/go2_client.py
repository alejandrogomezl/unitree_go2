# backend/go2_client.py
import asyncio
from typing import Optional, Dict, Any

from loguru import logger
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD
from aiortc import MediaStreamTrack

import cv2
import numpy as np


def parse_connection_method(method: str) -> WebRTCConnectionMethod:
    m = (method or "").strip().lower()
    if m in ("localap", "ap"):
        return WebRTCConnectionMethod.LocalAP
    if m in ("localsta", "sta", "local"):
        return WebRTCConnectionMethod.LocalSTA
    if m in ("remote", "cloud"):
        return WebRTCConnectionMethod.Remote
    return WebRTCConnectionMethod.LocalSTA


class Go2Client:
    """
    Envoltorio fino que copia la semántica de tu main.py:
    - connect(method, ip)  -> activa vídeo y registra callback (como en el ejemplo)
    - cmd(api_name)
    - send_move(x, y, z)
    - estop_soft(), stand(), sit(), etc.
    - disconnect() -> apaga canal de vídeo
    Además, mantiene el último frame JPEG en memoria para servirlo por FastAPI.
    """
    def __init__(self):
        self.conn: Optional[Go2WebRTCConnection] = None
        self.method: Optional[WebRTCConnectionMethod] = None
        self.ip: Optional[str] = None

        # (Opcional) credenciales/serial si un día usas Remote:
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.serial: Optional[str] = None

        # ---------- Buffers de vídeo ----------
        self._latest_jpeg: Optional[bytes] = None
        self._jpeg_lock = asyncio.Lock()
        self._frame_evt = asyncio.Event()
        self._video_started = asyncio.Event()
        self._watchdog_task: Optional[asyncio.Task] = None

    # ---------------- Conexión ----------------

    async def connect(self, method: str, ip: Optional[str] = None):
        """Crea la conexión EXACTAMENTE como en tu main.py, y engancha el vídeo como en el ejemplo."""
        self.method = parse_connection_method(method)
        self.ip = ip

        # Cierra si ya existía
        if self.conn:
            try:
                # intenta apagar vídeo si estaba encendido
                try:
                    self.conn.video.switchVideoChannel(False)
                except Exception:
                    pass
                await self.conn.close()
            except Exception:
                pass
            self.conn = None

        # Construcción calcada a tu script:
        if self.method == WebRTCConnectionMethod.Remote:
            self.conn = Go2WebRTCConnection(
                WebRTCConnectionMethod.Remote,
                serialNumber=self.serial,
                username=self.username,
                password=self.password,
            )
        elif self.method == WebRTCConnectionMethod.LocalAP:
            self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
        else:  # LocalSTA
            if self.ip:
                # Ojo: aquí usamos 'ip=' como en tu main.py
                self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=self.ip)
            else:
                self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        logger.info(f"Conectando al Go2 en modo {self.method.name}, ip={self.ip}")
        await self.conn.connect()
        await asyncio.sleep(0.1)  # respiro como tu main.py
        logger.success("Conectado al Go2 por WebRTC")

        # === ACTIVAR VÍDEO Y REGISTRAR CALLBACK (como en el ejemplo) ===
        try:
            self.conn.video.switchVideoChannel(True)
            logger.info("🎥 switchVideoChannel(True) enviado")

            async def recv_camera_stream(track: MediaStreamTrack):
                logger.info(f"📷 track recibido: kind={getattr(track, 'kind', '?')}")
                self._video_started.set()
                while True:
                    frame = await track.recv()                          # aiortc VideoFrame
                    img_bgr = frame.to_ndarray(format="bgr24")         # numpy BGR (como en tu ejemplo)
                    ok, enc = cv2.imencode(".jpg", img_bgr)            # JPEG con OpenCV
                    if not ok:
                        continue
                    data = enc.tobytes()
                    async with self._jpeg_lock:
                        self._latest_jpeg = data
                        self._frame_evt.set()
                        self._frame_evt.clear()

            # La librería invoca el callback como función normal -> creamos una task en el loop
            def on_track(track: MediaStreamTrack):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                loop.create_task(recv_camera_stream(track))

            self.conn.video.add_track_callback(on_track)
            logger.info("Callback de vídeo registrado (add_track_callback).")

            # Watchdog: si no llega track en 5 s, avisamos
            if self._watchdog_task:
                self._watchdog_task.cancel()
            self._watchdog_task = asyncio.create_task(self._video_watchdog())

        except Exception as e:
            logger.warning(f"No se pudo activar vídeo/callback: {e}")

    async def _video_watchdog(self):
        try:
            await asyncio.wait_for(self._video_started.wait(), timeout=5.0)
            logger.info("Video track activo ✅")
        except asyncio.TimeoutError:
            logger.warning(
                "No se recibió ningún video track en 5 s. "
                "Comprueba que la cámara del Go2 está habilitada y que la red permite el flujo de vídeo."
            )
        except asyncio.CancelledError:
            pass

    async def disconnect(self):
        if self.conn:
            try:
                try:
                    self.conn.video.switchVideoChannel(False)
                    logger.info("🎥 switchVideoChannel(False) enviado")
                except Exception:
                    pass
                await self.conn.close()
            except Exception:
                pass
            self.conn = None
            logger.info("Conexión WebRTC cerrada.")
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None
        self._video_started.clear()

    async def is_connected(self) -> bool:
        return self.conn is not None and self.conn.datachannel is not None

    # ---------------- SPORT (comandos) ----------------

    async def _publish(self, topic_key: str, payload: Dict[str, Any]):
        if not self.conn or not self.conn.datachannel:
            return
        await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC[topic_key], payload)

    async def cmd(self, api_name: str, parameter: Optional[dict] = None):
        """Envía un SPORT_CMD simple por SPORT_MOD (igual que en tu script)."""
        if not self.conn or not self.conn.datachannel:
            return
        if api_name not in SPORT_CMD:
            logger.warning(f"SPORT_CMD '{api_name}' no existe en esta versión del driver.")
            return
        payload = {"api_id": SPORT_CMD[api_name]}
        if parameter:
            payload["parameter"] = parameter
        await self._publish("SPORT_MOD", payload)

    async def send_move(self, x: float, y: float, z: float):
        """Move con parámetros x,y,z por SPORT_MOD (igual que tu main.py)."""
        if not self.conn or not self.conn.datachannel:
            return
        payload = {
            "api_id": SPORT_CMD["Move"],
            "parameter": {"x": float(x), "y": float(y), "z": float(z)},
        }
        await self._publish("SPORT_MOD", payload)

    async def estop_soft(self):
        await self.cmd("StopMove")

    async def stand(self):
        await self.cmd("StandUp")

    async def sit(self):
        # si tu firmware usa Sit (está en tu tabla), perfecto
        await self.cmd("Sit")

    async def standdown(self):
        await self.cmd("StandDown")

    async def frontjump(self):
        await self.cmd("FrontJump")

    async def hello(self):
        await self.cmd("Hello")

    async def fingerheart(self):
        await self.cmd("FingerHeart")

    async def stretch(self):
        await self.cmd("Stretch")

    async def dance1(self):
        await self.cmd("Dance1")

    # ---------------- Vídeo (último frame) ----------------

    async def get_latest_jpeg(self) -> Optional[bytes]:
        async with self._jpeg_lock:
            return self._latest_jpeg

    async def wait_for_frame(self, timeout: float = 2.0) -> Optional[bytes]:
        try:
            await asyncio.wait_for(self._frame_evt.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return await self.get_latest_jpeg()
