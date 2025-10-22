# backend/go2_client.py
import asyncio
from typing import Optional, Dict, Any

from loguru import logger
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

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
    - connect(method, ip)
    - cmd(api_name)
    - send_move(x, y, z)
    - estop_soft()
    - stand()/sit()
    - disconnect()
    """
    def __init__(self):
        self.conn: Optional[Go2WebRTCConnection] = None
        self.method: Optional[WebRTCConnectionMethod] = None
        self.ip: Optional[str] = None
        # (Opcional) credenciales/serial si un día usas Remote:
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.serial: Optional[str] = None

    async def connect(self, method: str, ip: Optional[str] = None):
        """Crea la conexión EXACTAMENTE como en tu main.py y espera lo justo."""
        self.method = parse_connection_method(method)
        self.ip = ip

        # Cierra si ya existía
        if self.conn:
            try:
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
                # Descubrimiento por SN si quisieras (dejado como placeholder):
                self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA)

        logger.info(f"Conectando al Go2 en modo {self.method.name}, ip={self.ip}")
        await self.conn.connect()

        # Tu main.py duerme ~0.1s tras connect() para dejar listo datachannel
        await asyncio.sleep(0.1)
        logger.success("Conectado al Go2 por WebRTC")

    async def disconnect(self):
        if self.conn:
            try:
                await self.conn.close()
            except Exception:
                pass
            self.conn = None
            logger.info("Conexión WebRTC cerrada.")

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
        # En tu main.py usas "StandUp"
        await self.cmd("StandUp")

    async def sit(self):
        # Si tu main.py usa "Sit" en vez de "StandDown", cámbialo aquí:
        # await self.cmd("Sit")
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