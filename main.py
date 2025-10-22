#!/usr/bin/env python3
import argparse
import asyncio
import time
from typing import Optional

import pygame
from loguru import logger

# === Imports exactos del proyecto original ===
from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection, WebRTCConnectionMethod
from go2_webrtc_driver.constants import RTC_TOPIC, SPORT_CMD


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def deadzone(v: float, dz: float) -> float:
    return 0.0 if abs(v) < dz else v


def parse_connection_method(s: str) -> WebRTCConnectionMethod:
    s = s.strip().lower()
    if s in ("localsta", "sta", "local"):
        return WebRTCConnectionMethod.LocalSTA
    if s in ("localap", "ap"):
        return WebRTCConnectionMethod.LocalAP
    if s in ("remote", "cloud"):
        return WebRTCConnectionMethod.Remote
    # por defecto, lo más típico si le pasas IP
    return WebRTCConnectionMethod.LocalSTA


class XboxTeleop:
    """
    Teleoperación del Unitree Go2 por WebRTC usando el driver original.

    Sticks:
      - LX (axis 0) -> y (lateral, derecha +)
      - LY (axis 1) -> x (avance, invertido: arriba +)
      - RX (axis 3) -> z (yaw, derecha +)

    Botones (índices típicos en Xbox con pygame):
      - A (0): StandUp
      - B (1): Sit
      - START (7): StopMove (frenada suave: x=y=z=0)
    """

    def __init__(
        self,
        ip: Optional[str],
        method: WebRTCConnectionMethod,
        rate_hz: float = 50.0,
        dz: float = 0.08,
        max_x: float = 0.7,     # m/s
        max_y: float = 0.5,     # m/s
        max_z: float = 1.5,     # rad/s
        username: Optional[str] = None,  # para Remote
        password: Optional[str] = None,  # para Remote
        serial: Optional[str] = None,    # ip o serial (para scan LocalSTA)
    ) -> None:
        self.period = 1.0 / rate_hz
        self.dz = dz
        self.max_x = max_x
        self.max_y = max_y
        self.max_z = max_z

        self.method = method
        self.ip = ip
        self.username = username
        self.password = password
        self.serial = serial

        self.conn: Optional[Go2WebRTCConnection] = None
        self.running = True

    async def connect(self) -> None:
        # Construye la conexión EXACTAMENTE como en el driver original
        if self.method == WebRTCConnectionMethod.Remote:
            self.conn = Go2WebRTCConnection(
                WebRTCConnectionMethod.Remote,
                serialNumber=self.serial,
                username=self.username,
                password=self.password,
            )
        elif self.method == WebRTCConnectionMethod.LocalAP:
            # En LocalAP el driver fija ip=192.168.12.1; da igual lo que pases
            self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalAP)
        else:
            # LocalSTA: o bien por IP (recomendado), o por SN + discovery
            if self.ip:
                self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=self.ip)
            else:
                self.conn = Go2WebRTCConnection(WebRTCConnectionMethod.LocalSTA, serialNumber=self.serial)

        logger.info(f"Connecting via {self.method.name} (ip={self.ip}, sn={self.serial}) ...")
        await self.conn.connect()
        # Espera a que el datachannel esté “open” (el driver lo abstrae, pero damos tiempo)
        await asyncio.sleep(0.1)
        logger.success("WebRTC connected.")

    async def send_move(self, x: float, y: float, z: float) -> None:
        """
        Publica el comando Move en el topic SPORT_MOD, como hace el ejemplo oficial:
            api_id: SPORT_CMD["Move"]
            parameter: {"x": x, "y": y, "z": z}
        """
        if not self.conn or not self.conn.datachannel:
            return
        payload = {
            "api_id": SPORT_CMD["Move"],
            "parameter": {"x": float(x), "y": float(y), "z": float(z)},
        }
        await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], payload)

    async def cmd(self, api_name: str, parameter: Optional[dict] = None) -> None:
        """Lanza cualquier SPORT_CMD simple por topic SPORT_MOD."""
        if not self.conn or not self.conn.datachannel:
            return
        if api_name not in SPORT_CMD:
            logger.warning(f"SPORT_CMD '{api_name}' no existe en esta versión del driver.")
            return
        payload = {"api_id": SPORT_CMD[api_name]}
        if parameter:
            payload["parameter"] = parameter
        await self.conn.datachannel.pub_sub.publish_request_new(RTC_TOPIC["SPORT_MOD"], payload)

    async def estop_soft(self) -> None:
        await self.cmd("StopMove")
        # además envía una última velocidad 0 por seguridad
        await self.send_move(0.0, 0.0, 0.0)

    def read_axes(self, js: pygame.joystick.Joystick) -> tuple[float, float, float]:
        # Índices habituales en Xbox:
        # axis 0: LX, axis 1: LY, axis 3: RX
        lx = js.get_axis(0)
        ly = js.get_axis(1)
        rx = js.get_axis(3)

        # Deadzone + escalado
        x = deadzone(-ly, self.dz) * self.max_x   # arriba + => avance +
        y = deadzone(lx,  self.dz) * self.max_y   # derecha + => lateral +
        z = deadzone(rx,  self.dz) * self.max_z   # derecha + => yaw +
        return x, y, z

    async def run(self) -> None:
        # Init pygame
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            logger.error("No se detectó mando. Conéctalo por USB o Bluetooth y vuelve a ejecutar.")
            return
        js = pygame.joystick.Joystick(0)
        js.init()
        logger.success(f"Usando mando: {js.get_name()}")

        # Conecta WebRTC
        await self.connect()

        # (Opcional) sube a StandUp al iniciar
        await self.cmd("StandUp")
        last = 0.0

        try:
            while self.running:
                # Eventos de botones
                for event in pygame.event.get():
                    if event.type == pygame.JOYBUTTONDOWN:
                        btn = event.button
                        if btn == 0:        # A
                            await self.cmd("StandUp")
                        elif btn == 1:      # B
                            await self.cmd("Sit")
                        elif btn == 7:      # START
                            await self.estop_soft()

                # Envío periódico de velocidades
                now = time.time()
                if now - last >= self.period:
                    x, y, z = self.read_axes(js)
                    await self.send_move(x, y, z)
                    last = now

                await asyncio.sleep(0.0)

        except KeyboardInterrupt:
            logger.info("Interrumpido por usuario.")
        finally:
            try:
                await self.estop_soft()
            except Exception:
                pass
            if self.conn:
                await self.conn.disconnect()
            pygame.quit()
            logger.info("Cerrado correctamente.")


def main():
    parser = argparse.ArgumentParser(description="Teleop Xbox → Unitree Go2 (WebRTC, driver original)")
    parser.add_argument("--ip", help="IP del robot (para LocalSTA). Ej: 192.168.12.1")
    parser.add_argument("--serial", help="Número de serie (para LocalSTA discovery o Remote)")
    parser.add_argument("--method", default="localsta", help="localsta | localap | remote")
    parser.add_argument("--rate", type=float, default=50.0, help="Frecuencia de envío (Hz)")
    parser.add_argument("--dz", type=float, default=0.08, help="Deadzone del stick [0..1]")
    parser.add_argument("--max-x", type=float, default=0.7, help="Vel. lineal X máx (m/s)")
    parser.add_argument("--max-y", type=float, default=0.5, help="Vel. lineal Y máx (m/s)")
    parser.add_argument("--max-z", type=float, default=1.5, help="Vel. angular Z máx (rad/s)")
    parser.add_argument("--username", help="(Remote) Usuario Unitree")
    parser.add_argument("--password", help="(Remote) Password Unitree")
    args = parser.parse_args()

    method = parse_connection_method(args.method)

    # Validaciones mínimas
    if method == WebRTCConnectionMethod.LocalSTA and not (args.ip or args.serial):
        logger.warning("LocalSTA: proporciona --ip (recomendado) o --serial para discovery.")
    if method == WebRTCConnectionMethod.Remote and not (args.serial and args.username and args.password):
        logger.error("Remote: necesitas --serial, --username y --password.")
        return

    teleop = XboxTeleop(
        ip=args.ip,
        method=method,
        rate_hz=args.rate,
        dz=args.dz,
        max_x=args.max_x,
        max_y=args.max_y,
        max_z=args.max_z,
        username=args.username,
        password=args.password,
        serial=args.serial,
    )
    asyncio.run(teleop.run())


if __name__ == "__main__":
    main()
