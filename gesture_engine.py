"""Motor de gestos de mano para GestureCube UNO Q.

Usa MediaPipe Tasks (HandLandmarker) en modo VIDEO, 100 % local.
No depende de la API legacy `mediapipe.solutions`, que no está disponible
en MediaPipe 1.2.x.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import time
import types
from collections import deque
from dataclasses import dataclass
from typing import Deque

import numpy as np

# MediaPipe importa matplotlib.pyplot desde drawing_utils, pero solo lo usa
# en funciones de dibujo que no empleamos. Si matplotlib no está instalado,
# inyectamos un stub mínimo para evitar una dependencia pesada.
if importlib.util.find_spec("matplotlib") is None:
    _mpl = types.ModuleType("matplotlib")
    _mpl.__path__ = []  # type: ignore[attr-defined]
    _pyplot = types.ModuleType("matplotlib.pyplot")
    _mpl.pyplot = _pyplot  # type: ignore[attr-defined]
    sys.modules.setdefault("matplotlib", _mpl)
    sys.modules.setdefault("matplotlib.pyplot", _pyplot)

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    MEDIAPIPE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - se informa en runtime
    mp = None
    mp_python = None
    vision = None
    MEDIAPIPE_AVAILABLE = False
    MEDIAPIPE_IMPORT_ERROR = str(exc)
else:
    MEDIAPIPE_IMPORT_ERROR = ""


# Conexiones del esqueleto de la mano (21 landmarks).
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

FINGER_TIPS = (8, 12, 16, 20)
FINGER_PIPS = (6, 10, 14, 18)

# Distancia mínima (en ancho normalizado) para considerar un barrido.
SWIPE_MIN_DX = 0.17
SWIPE_WINDOW_S = 0.60
SWIPE_COOLDOWN_S = 0.90
SWIPE_MIN_SPEED = 0.32  # ancho normalizado por segundo

# Frames consecutivos para confirmar puño/palma.
STABLE_FRAMES = 4


@dataclass
class HandState:
    handedness: str
    score: float
    landmarks: list[tuple[float, float, float]]
    gesture: str
    fingers: int
    palm: tuple[float, float]

    def to_dict(self) -> dict:
        return {
            "handedness": self.handedness,
            "score": round(float(self.score), 3),
            "gesture": self.gesture,
            "fingers": int(self.fingers),
            "palm": [round(float(self.palm[0]), 4), round(float(self.palm[1]), 4)],
            "landmarks": [
                [round(float(x), 4), round(float(y), 4), round(float(z), 4)]
                for x, y, z in self.landmarks
            ],
        }


@dataclass
class GestureEvent:
    action: str
    hand: str
    value: float = 0.0
    timestamp: float = 0.0


class GestureEngine:
    """Detecta manos y gestos sobre frames BGR de OpenCV."""

    def __init__(self, model_path: str, num_hands: int = 2) -> None:
        if not MEDIAPIPE_AVAILABLE:
            raise RuntimeError(f"MediaPipe no disponible: {MEDIAPIPE_IMPORT_ERROR}")

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = 0
        self._tracks: dict[str, Deque[tuple[float, float, float, str]]] = {
            "Left": deque(maxlen=48),
            "Right": deque(maxlen=48),
        }
        self._last_seen: dict[str, float] = {"Left": 0.0, "Right": 0.0}
        self._cooldown_until: dict[str, float] = {"Left": 0.0, "Right": 0.0}
        self._stable: dict[str, str | None] = {"Left": None, "Right": None}
        self._stable_count: dict[str, int] = {"Left": 0, "Right": 0}
        self._spin_active = False

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------
    def process(
        self,
        frame_bgr: np.ndarray,
        now: float | None = None,
    ) -> tuple[list[HandState], list[GestureEvent]]:
        """Procesa un frame y devuelve manos detectadas + eventos de gesto."""
        if now is None:
            now = time.monotonic()

        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, self._next_timestamp_ms())

        hands: list[HandState] = []
        events: list[GestureEvent] = []
        seen: set[str] = set()

        for index, landmarks in enumerate(result.hand_landmarks or []):
            handedness = "Right"
            score = 0.0
            if result.handedness and index < len(result.handedness):
                categories = result.handedness[index]
                if categories:
                    handedness = categories[0].category_name or "Right"
                    score = float(categories[0].score or 0.0)

            points = [(float(lm.x), float(lm.y), float(lm.z)) for lm in landmarks]
            palm = (
                sum(points[i][0] for i in (0, 5, 9, 13, 17)) / 5.0,
                sum(points[i][1] for i in (0, 5, 9, 13, 17)) / 5.0,
            )
            fingers = self._count_extended(points)
            gesture = self._classify(fingers)
            hand = HandState(
                handedness=handedness,
                score=score,
                landmarks=points,
                gesture=gesture,
                fingers=fingers,
                palm=palm,
            )
            hands.append(hand)
            seen.add(handedness)
            self._last_seen[handedness] = now
            self._tracks[handedness].append((now, palm[0], palm[1], gesture))

            events.extend(self._detect_swipe(handedness, palm, gesture, now))
            events.extend(self._detect_static(handedness, gesture, now))

        # Limpiar pistas de manos que desaparecieron.
        for handedness in ("Left", "Right"):
            if handedness not in seen and now - self._last_seen[handedness] > 0.6:
                self._tracks[handedness].clear()
                self._stable[handedness] = None
                self._stable_count[handedness] = 0

        # Si el puño que inició el giro desaparece, detener el giro.
        if (
            self._spin_active
            and "Right" not in seen
            and now - self._last_seen["Right"] > 1.2
        ):
            self._spin_active = False
            events.append(GestureEvent("spin_stop", "Right", 0.0, now))

        return hands, events

    def close(self) -> None:
        try:
            self._landmarker.close()
        except Exception:
            pass

    def mark_spin_stopped(self) -> None:
        """Sincroniza el estado interno cuando el servidor detiene el giro."""
        self._spin_active = False

    # ------------------------------------------------------------------
    # Clasificación de dedos / gesto estático
    # ------------------------------------------------------------------
    @staticmethod
    def _count_extended(points: list[tuple[float, float, float]]) -> int:
        wrist = np.array(points[0], dtype=np.float32)
        count = 0
        for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
            d_tip = float(np.linalg.norm(np.array(points[tip], dtype=np.float32) - wrist))
            d_pip = float(np.linalg.norm(np.array(points[pip], dtype=np.float32) - wrist))
            if d_pip > 1e-6 and d_tip > d_pip * 1.15:
                count += 1
        return count

    @staticmethod
    def _classify(fingers: int) -> str:
        if fingers <= 1:
            return "fist"
        if fingers >= 3:
            return "open"
        return "unknown"

    def _detect_static(
        self,
        handedness: str,
        gesture: str,
        now: float,
    ) -> list[GestureEvent]:
        if gesture == self._stable[handedness]:
            self._stable_count[handedness] += 1
        else:
            self._stable[handedness] = gesture
            self._stable_count[handedness] = 1

        if self._stable_count[handedness] < STABLE_FRAMES:
            return []

        events: list[GestureEvent] = []
        if gesture == "fist" and handedness == "Right" and not self._spin_active:
            self._spin_active = True
            events.append(GestureEvent("spin_start", handedness, 0.0, now))
        elif gesture == "open" and self._spin_active:
            self._spin_active = False
            events.append(GestureEvent("spin_stop", handedness, 0.0, now))
        return events

    # ------------------------------------------------------------------
    # Barridos horizontales
    # ------------------------------------------------------------------
    def _detect_swipe(
        self,
        handedness: str,
        palm: tuple[float, float],
        gesture: str,
        now: float,
    ) -> list[GestureEvent]:
        if gesture != "open":
            return []
        if now < self._cooldown_until[handedness]:
            return []

        track = self._tracks[handedness]
        if len(track) < 5:
            return []

        reference = None
        for t, x, y, _g in track:
            if now - t >= SWIPE_WINDOW_S * 0.75:
                reference = (t, x, y)
            else:
                break
        if reference is None:
            return []

        dt = max(now - reference[0], 1e-3)
        dx = palm[0] - reference[1]
        dy = palm[1] - reference[2]
        speed = abs(dx) / dt

        if abs(dx) < SWIPE_MIN_DX:
            return []
        if abs(dx) < abs(dy) * 1.45:
            return []
        if speed < SWIPE_MIN_SPEED:
            return []

        direction = "left" if dx < 0 else "right"
        self._cooldown_until[handedness] = now + SWIPE_COOLDOWN_S
        track.clear()
        return [GestureEvent(f"swipe_{direction}", handedness, abs(dx), now)]

    # ------------------------------------------------------------------
    def _next_timestamp_ms(self) -> int:
        timestamp = int(time.monotonic() * 1000)
        if timestamp <= self._last_timestamp_ms:
            timestamp = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp
        return timestamp
