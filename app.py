#!/usr/bin/env python3
"""GestureCube UNO Q.

Servidor HTTP liviano (stdlib) + cámara USB + MediaPipe HandLandmarker.
Sirve una página con un cubo Rubik 3D y transmite los gestos por SSE.

No usa FastAPI ni frameworks externos: solo OpenCV, NumPy y MediaPipe.
"""

from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

try:
    import cv2
except Exception as exc:  # pragma: no cover
    cv2 = None
    CV2_IMPORT_ERROR = str(exc)
else:
    CV2_IMPORT_ERROR = ""

from gesture_engine import (
    GestureEngine,
    HAND_CONNECTIONS,
    HandState,
    MEDIAPIPE_AVAILABLE,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_MODEL = BASE_DIR / "static" / "models" / "hand_landmarker.task"
DEFAULT_PORT = 8091

STATE: "AppState"
CAMERA: "CameraWorker | None" = None


# ---------------------------------------------------------------------------
# Estado compartido
# ---------------------------------------------------------------------------
class AppState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.started_at = time.time()
        self.camera_ok = False
        self.camera_name = ""
        self.camera_error = "Buscando cámara USB..."
        self.model_ok = False
        self.model_error = ""
        self.fps = 0.0
        self.hands: list[dict] = []
        self.gesture = "idle"
        self.spin = False
        self.last_event: dict | None = None
        self.last_event_at = 0.0
        self.seq = 0
        self.latest_jpeg: bytes | None = None
        self.last_frame_at = 0.0
        self.last_hand_at = 0.0

    def set_camera(self, ok: bool, name: str = "", error: str = "") -> None:
        with self.lock:
            self.camera_ok = ok
            self.camera_name = name
            self.camera_error = error

    def set_frame(self, jpeg: bytes, at: float | None = None) -> None:
        with self.lock:
            self.latest_jpeg = jpeg
            self.last_frame_at = at or time.time()

    def set_fps(self, fps: float) -> None:
        with self.lock:
            self.fps = fps if self.fps <= 0 else (self.fps * 0.85 + fps * 0.15)

    def set_hands(self, hands: list[HandState]) -> None:
        with self.lock:
            self.hands = [hand.to_dict() for hand in hands]
            if hands:
                self.last_hand_at = time.time()

    def set_gesture(self, hands: list[HandState]) -> None:
        with self.lock:
            # Mantener visible la acción recién disparada durante 1.5 s.
            if time.time() - self.last_event_at < 1.5:
                return
            if hands:
                self.gesture = hands[0].gesture
            elif self.spin:
                self.gesture = "spin"
            else:
                self.gesture = "idle"

    def push_event(self, action: str, hand: str, value: float = 0.0) -> None:
        """Traduce un gesto crudo a una acción de la interfaz."""
        with self.lock:
            mapped = action
            if action == "swipe_left":
                mapped = "rotate_left" if hand == "Right" else "rotate_right"
            elif action == "swipe_right":
                mapped = "rotate_right" if hand == "Right" else "rotate_left"
            elif action == "spin_start":
                self.spin = True
            elif action == "spin_stop":
                self.spin = False

            self.seq += 1
            self.last_event_at = time.time()
            self.gesture = mapped
            self.last_event = {
                "action": mapped,
                "raw": action,
                "hand": hand,
                "value": round(float(value), 4),
                "at": time.time(),
                "seq": self.seq,
            }

    def reset(self) -> None:
        with self.lock:
            self.spin = False
            self.gesture = "idle"
            self.seq += 1
            self.last_event = {
                "action": "reset",
                "raw": "reset",
                "hand": "demo",
                "value": 0.0,
                "at": time.time(),
                "seq": self.seq,
            }

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "ok": True,
                "camera": self.camera_ok,
                "camera_name": self.camera_name,
                "camera_error": self.camera_error,
                "model": self.model_ok,
                "model_error": self.model_error,
                "browser_model": (STATIC_DIR / "models" / "hand_landmarker.task").is_file(),
                "fps": round(self.fps, 1),
                "hands": self.hands,
                "hand_count": len(self.hands),
                "gesture": self.gesture,
                "spin": self.spin,
                "last_event": self.last_event,
                "seq": self.seq,
                "uptime": int(time.time() - self.started_at),
            }


# ---------------------------------------------------------------------------
# Cámara + inferencia
# ---------------------------------------------------------------------------
class CameraWorker(threading.Thread):
    def __init__(
        self,
        state: AppState,
        engine: GestureEngine | None,
        camera_spec: str | None = None,
        mirror: bool = True,
    ) -> None:
        super().__init__(name="gesturecube-camera", daemon=True)
        self.state = state
        self.engine = engine
        self.camera_spec = camera_spec
        self.mirror = mirror
        self.stop_event = threading.Event()
        self.cap = None
        self.camera_name = ""

    # -- apertura ---------------------------------------------------------
    def _open_camera(self):
        if cv2 is None:
            self.state.set_camera(False, "", f"OpenCV no disponible: {CV2_IMPORT_ERROR}")
            return None

        if self.camera_spec:
            cap, name = self._try_capture(self.camera_spec)
            if cap is not None:
                return cap, name
            self.state.set_camera(False, "", f"No se pudo abrir la cámara: {self.camera_spec}")
            return None

        for index in range(10):
            device = f"/dev/video{index}"
            if not os.path.exists(device):
                continue
            name = self._video_name(index)
            lowered = name.lower()
            if any(token in lowered for token in ("venus", "encoder", "decoder", "qcom")):
                continue
            cap, opened_name = self._try_capture(index)
            if cap is not None:
                return cap, opened_name or name or device

        self.state.set_camera(
            False,
            "",
            "No se detectó cámara UVC. Conectá la cámara al hub USB-C con alimentación.",
        )
        return None

    def _try_capture(self, spec):
        if cv2 is None:
            return None, ""
        try:
            if isinstance(spec, str) and spec.isdigit():
                spec = int(spec)
            cap = cv2.VideoCapture(spec, cv2.CAP_V4L2) if isinstance(spec, int) else cv2.VideoCapture(spec)
            if not cap.isOpened():
                cap.release()
                return None, ""
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                return None, ""
            if isinstance(spec, int):
                name = self._video_name(spec)
            else:
                name = str(spec)
            return cap, name
        except Exception:
            return None, ""

    @staticmethod
    def _video_name(index: int) -> str:
        path = Path(f"/sys/class/video4linux/video{index}/name")
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return f"/dev/video{index}"

    # -- loop -------------------------------------------------------------
    def run(self) -> None:
        while not self.stop_event.is_set():
            opened = self._open_camera()
            if opened is None:
                self._publish_placeholder()
                self.stop_event.wait(5.0)
                continue

            self.cap, self.camera_name = opened
            self.state.set_camera(True, self.camera_name, "")
            logging.info("Cámara abierta: %s", self.camera_name)
            failures = 0
            last_placeholder = 0.0

            while not self.stop_event.is_set():
                loop_start = time.time()
                ok, frame = self.cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures > 25:
                        logging.warning("La cámara dejó de entregar frames; reintentando")
                        break
                    time.sleep(0.04)
                    continue
                failures = 0

                if self.mirror:
                    frame = cv2.flip(frame, 1)

                hands: list[HandState] = []
                if self.engine is not None:
                    try:
                        hands, events = self.engine.process(frame, now=time.monotonic())
                        for event in events:
                            self.state.push_event(event.action, event.hand, event.value)
                    except Exception:
                        logging.exception("Error procesando el frame")
                        hands = []

                self._draw_overlay(frame, hands)
                ok, encoded = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82]
                )
                if ok:
                    self.state.set_frame(encoded.tobytes(), time.time())
                self.state.set_hands(hands)
                self.state.set_gesture(hands)

                elapsed = max(time.time() - loop_start, 1e-3)
                self.state.set_fps(1.0 / elapsed)

                # Si el puño desaparece, el giro se detiene solo.
                if self.state.spin and not hands:
                    with self.state.lock:
                        lost_for = time.time() - self.state.last_hand_at
                    if lost_for > 3.5:
                        self.state.push_event("spin_stop", "auto")

                # Placeholder si la cámara se cuelga.
                if time.time() - last_placeholder > 2.0 and not hands:
                    last_placeholder = time.time()

                # Limitar a ~20 fps para no saturar la placa.
                sleep_for = max(0.0, 1.0 / 20.0 - (time.time() - loop_start))
                if sleep_for:
                    time.sleep(sleep_for)

            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.state.set_camera(False, "", "Cámara desconectada; reintentando...")
            self.stop_event.wait(2.0)

        if self.cap is not None:
            self.cap.release()
            self.cap = None

    # -- dibujo -----------------------------------------------------------
    def _publish_placeholder(self) -> None:
        if cv2 is None:
            return
        frame = self._make_placeholder()
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ok:
            self.state.set_frame(encoded.tobytes(), time.time())

    @staticmethod
    def _make_placeholder():
        w, h = 640, 480
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (8, 12, 20)
        # Rejilla tenue.
        for x in range(0, w, 40):
            cv2.line(frame, (x, 0), (x, h), (16, 24, 38), 1)
        for y in range(0, h, 40):
            cv2.line(frame, (0, y), (w, y), (16, 24, 38), 1)
        # Esquinas.
        color = (0, 220, 255)
        length = 34
        for (x, y, dx, dy) in (
            (24, 24, 1, 1), (w - 24, 24, -1, 1),
            (24, h - 24, 1, -1), (w - 24, h - 24, -1, -1),
        ):
            cv2.line(frame, (x, y), (x + dx * length, y), color, 2)
            cv2.line(frame, (x, y), (x, y + dy * length), color, 2)
        cv2.putText(frame, "CAMARA USB NO DETECTADA", (120, 205),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.95, (235, 245, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, "Conecta la camara al hub USB-C", (150, 250),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (150, 175, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, "con alimentacion externa (PD)", (165, 278),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (150, 175, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, "El servicio la detecta automaticamente", (135, 330),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1, cv2.LINE_AA)
        return frame

    @staticmethod
    def _draw_overlay(frame, hands: list[HandState]) -> None:
        h, w = frame.shape[:2]
        for hand in hands:
            color = (0, 220, 255) if hand.handedness == "Right" else (255, 80, 200)
            points = [(int(x * w), int(y * h)) for x, y, _z in hand.landmarks]
            for a, b in HAND_CONNECTIONS:
                if a < len(points) and b < len(points):
                    cv2.line(frame, points[a], points[b], color, 2, cv2.LINE_AA)
            for x, y in points:
                cv2.circle(frame, (x, y), 4, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), 5, color, 1, cv2.LINE_AA)
            label = f"{hand.handedness.upper()}  {hand.gesture.upper()}  {hand.fingers} dedos"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            x0, y0 = 18, 18
            cv2.rectangle(frame, (x0 - 8, y0 - 6), (x0 + tw + 8, y0 + th + 8), (5, 8, 14), -1)
            cv2.putText(frame, label, (x0, y0 + th), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "GestureCube/1.0"

    def log_message(self, fmt, *args):
        logging.debug("%s - %s", self.address_string(), fmt % args)

    # -- helpers ----------------------------------------------------------
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, relative: str) -> None:
        if not relative:
            relative = "index.html"
        candidate = (STATIC_DIR / relative).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_text("Forbidden", 403)
            return
        if not candidate.is_file():
            self._send_text("Not found", 404)
            return
        data = candidate.read_bytes()
        mime, _ = mimetypes.guess_type(str(candidate))
        mime = mime or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # -- GET --------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self._serve_file("index.html")
        elif path.startswith("/static/"):
            self._serve_file(path[len("/static/"):])
        elif path == "/video":
            self._stream_video()
        elif path == "/events":
            self._stream_events()
        elif path == "/api/state":
            self._send_json(STATE.snapshot())
        elif path == "/healthz":
            snap = STATE.snapshot()
            self._send_json({
                "ok": True,
                "camera": snap["camera"],
                "model": snap["model"],
                "browser_model": snap["browser_model"],
                "fps": snap["fps"],
                "hands": snap["hand_count"],
                "gesture": snap["gesture"],
                "spin": snap["spin"],
                "uptime": snap["uptime"],
            })
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._send_text("Not found", 404)

    def _stream_video(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                with STATE.lock:
                    jpeg = STATE.latest_jpeg
                if jpeg:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                    self.wfile.write(jpeg)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                time.sleep(1.0 / 15.0)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _stream_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while True:
                payload = json.dumps(STATE.snapshot(), ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.25)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    # -- POST -------------------------------------------------------------
    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length:
            self.rfile.read(min(length, 65536))

        demo = {
            "right_swipe_left": ("swipe_left", "Right"),
            "right_swipe_right": ("swipe_right", "Right"),
            "left_swipe_right": ("swipe_right", "Left"),
            "left_swipe_left": ("swipe_left", "Left"),
            "right_fist": ("spin_start", "Right"),
            "open_palm": ("spin_stop", "Right"),
            "spin_stop": ("spin_stop", "Right"),
        }

        if path.startswith("/api/demo/"):
            action = path[len("/api/demo/"):]
            if action == "reset":
                STATE.reset()
                self._send_json({"ok": True, "event": STATE.snapshot()["last_event"]})
                return
            if action in demo:
                raw, hand = demo[action]
                STATE.push_event(raw, hand)
                self._send_json({"ok": True, "event": STATE.snapshot()["last_event"]})
                return
            self._send_json({"ok": False, "error": "acción desconocida"}, 400)
            return

        if path == "/api/reset":
            STATE.reset()
            self._send_json({"ok": True})
            return

        self._send_text("Not found", 404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    global STATE, CAMERA

    parser = argparse.ArgumentParser(description="GestureCube UNO Q")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--camera", default=os.environ.get("GESTURECUBE_CAMERA"))
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--no-mirror", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    STATE = AppState()
    engine = None
    model_path = Path(args.model)
    if not MEDIAPIPE_AVAILABLE:
        STATE.model_error = (
            "MediaPipe nativo no disponible en este CPU; "
            "la inferencia corre en el navegador"
        )
        logging.info(STATE.model_error)
    elif model_path.is_file():
        try:
            engine = GestureEngine(str(model_path))
            STATE.model_ok = True
            logging.info("MediaPipe HandLandmarker cargado: %s", model_path)
        except Exception as exc:
            STATE.model_error = str(exc)
            logging.warning("No se pudo cargar el motor nativo: %s", exc)
    else:
        STATE.model_error = f"Modelo no encontrado: {model_path}"
        logging.error(STATE.model_error)

    CAMERA = CameraWorker(
        STATE,
        engine,
        camera_spec=args.camera,
        mirror=not args.no_mirror,
    )
    CAMERA.start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True

    def _shutdown(_signum, _frame):
        logging.info("Deteniendo GestureCube...")
        if CAMERA is not None:
            CAMERA.stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logging.info("GestureCube escuchando en http://%s:%s", args.host, args.port)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        if CAMERA is not None:
            CAMERA.stop_event.set()
            CAMERA.join(timeout=3.0)
        if engine is not None:
            engine.close()
        server.server_close()
        logging.info("GestureCube detenido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
