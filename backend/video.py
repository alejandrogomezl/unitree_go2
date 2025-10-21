from __future__ import annotations
import time
import threading
import cv2
import numpy as np
from typing import Optional, Callable
from loguru import logger


class VideoBuffer:
    """
    Guarda el último frame (BGR) y lo expone como JPEG.
    Thread-safe, bajo consumo.
    """
    def __init__(self, width: int = 640, height: int = 360):
        self._lock = threading.Lock()
        self._frame_bgr: Optional[np.ndarray] = None
        self._width = width
        self._height = height
        # placeholder inicial
        self.set_placeholder("No video")

    def set_placeholder(self, text: str = "No video"):
        img = np.zeros((self._height, self._width, 3), dtype=np.uint8)
        cv2.putText(img, text, (20, self._height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2, cv2.LINE_AA)
        with self._lock:
            self._frame_bgr = img

    def set_frame_bgr(self, frame_bgr: np.ndarray):
        if frame_bgr is None:
            return
        # opcional: redimensiona para ahorrar ancho de banda
        if frame_bgr.shape[1] != self._width or frame_bgr.shape[0] != self._height:
            frame_bgr = cv2.resize(frame_bgr, (self._width, self._height))
        with self._lock:
            self._frame_bgr = frame_bgr

    def get_jpeg(self, quality: int = 80) -> bytes:
        with self._lock:
            frame = self._frame_bgr.copy() if self._frame_bgr is not None else None
        if frame is None:
            self.set_placeholder("No video")
            with self._lock:
                frame = self._frame_bgr.copy()
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return buf.tobytes() if ok else b""


# Singleton global para el vídeo
VIDEO_BUFFER = VideoBuffer()


class Go2VideoBridge:
    """
    Intenta engancharse a la fuente de vídeo del driver.
    - Si el driver expone callbacks, nos suscribimos.
    - Si no, mantenemos placeholder (sin errores).
    """
    def __init__(self, conn):
        self.conn = conn
        self._attached = False

    def attach(self):
        """
        Llama tras conectar WebRTC. Intenta detectar puntos de extensión comunes.
        No falla si no hay vídeo: deja placeholder.
        """
        try:
            # Caso A: atributo 'on_video_frame' (callable) => asignable
            if hasattr(self.conn, "on_video_frame"):
                handler = self._make_handler()
                setattr(self.conn, "on_video_frame", handler)
                self._attached = True
                logger.info("VideoBridge: usando conn.on_video_frame callback.")
                return

            # Caso B: self.conn.media.add_video_callback(handler)
            media = getattr(self.conn, "media", None)
            if media is not None:
                add_cb = getattr(media, "add_video_callback", None)
                if callable(add_cb):
                    add_cb(self._make_handler())
                    self._attached = True
                    logger.info("VideoBridge: usando media.add_video_callback().")
                    return

            # Caso C: self.conn.video_track con frames PyAV (frame.to_ndarray(format='bgr24'))
            vtrack = getattr(self.conn, "video_track", None)
            if vtrack is not None:
                # Si el driver no provee callback directo, no forzamos consumir aquí;
                # dependemos del callback del driver. Deja placeholder.
                logger.warning("VideoBridge: video_track detectado pero sin callback directo.")
                return

            logger.warning("VideoBridge: no se encontró API de vídeo en el driver. Se mantiene placeholder.")
        except Exception as e:
            logger.exception(f"VideoBridge.attach() error: {e}")

    def _make_handler(self) -> Callable:
        """
        Devuelve un callback que acepta:
          - numpy ndarray BGR
          - o PyAV VideoFrame (frame.to_ndarray('bgr24'))
        """
        def _handler(frame):
            try:
                # PyAV VideoFrame
                if hasattr(frame, "to_ndarray"):
                    bgr = frame.to_ndarray(format="bgr24")
                else:
                    bgr = frame
                if isinstance(bgr, np.ndarray):
                    VIDEO_BUFFER.set_frame_bgr(bgr)
            except Exception as e:
                logger.exception(f"Video handler error: {e}")
        return _handler
