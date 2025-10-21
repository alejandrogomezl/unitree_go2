from typing import Optional
from loguru import logger
from .video import Go2VideoBridge, VIDEO_BUFFER
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD

def parse_method(method: str) -> WebRTCConnectionMethod:
    m = (method or "").lower()
    if m in ("localap", "ap"): return WebRTCConnectionMethod.LocalAP
    if m in ("localsta", "sta", "local"): return WebRTCConnectionMethod.LocalSTA
    if m in ("remote", "cloud"): return WebRTCConnectionMethod.Remote
    return WebRTCConnectionMethod.LocalSTA

class Go2Client:
    def __init__(self, method: str, ip: Optional[str] = None):
        self.method = parse_method(method)
        self.ip = ip
        self.conn: Optional[Go2WebRTCConnection] = None

    async def connect(self):
        if self.method == WebRTCConnectionMethod.LocalAP:
            self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
        else:
            self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=self.ip)
        logger.info(f"Conectando al Go2 en modo {self.method.name}, ip={self.ip}")
        await self.conn.connect()
        logger.success("Conectado al Go2 por WebRTC")
        try:
            Go2VideoBridge(self.conn).attach()
            VIDEO_BUFFER.set_placeholder("Conectado (sin frames aún)")
        except Exception as e:
            logger.exception(f"No se pudo adjuntar el vídeo: {e}")
            
    def get_connection(self):
        return self.conn

    async def disconnect(self):
        if self.conn:
            await self.conn.disconnect()
            logger.info("Conexión WebRTC cerrada.")
            self.conn = None

    async def move(self, x: float, y: float, z: float):
        if not self.conn or not self.conn.datachannel:
            return
        payload = {"api_id": SPORT_CMD["Move"], "parameter": {"x": x, "y": y, "z": z}}
        await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], payload)

    async def command(self, cmd: str):
        if not self.conn or not self.conn.datachannel:
            return
        if cmd not in SPORT_CMD:
            logger.warning(f"Comando {cmd} no existe.")
            return
        await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD[cmd]})
