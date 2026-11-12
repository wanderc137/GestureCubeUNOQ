import { FilesetResolver, HandLandmarker } from "./mediapipe/vision_bundle.mjs";

// =====================================================================
// GestureCube UNO Q — página de demo
// La cámara y el servidor corren en la UNO Q. La inferencia de manos corre
// en el navegador con MediaPipe Tasks Vision (WASM), servido localmente.
// =====================================================================

// ---------------------------------------------------------------------
// Cubo Rubik 3D en CSS
// ---------------------------------------------------------------------
const CUBIE = 54;
const STEP = 58;
const INNER = "#0a0f19";
const COLORS = {
  front: "#ff3b3b",
  back: "#ff9f1c",
  right: "#38d66b",
  left: "#2f7bff",
  top: "#f4f7ff",
  bottom: "#ffd23f",
};

const cube = document.getElementById("cube");
const cubeScene = document.getElementById("cube-scene");
const stageLabel = document.getElementById("stage-label");
const gestureCards = Array.from(document.querySelectorAll(".gesture-card"));

const FACES = [
  ["front", (x, y, z) => z === 1, `translateZ(${CUBIE / 2}px)`],
  ["back", (x, y, z) => z === -1, `rotateY(180deg) translateZ(${CUBIE / 2}px)`],
  ["right", (x, y, z) => x === 1, `rotateY(90deg) translateZ(${CUBIE / 2}px)`],
  ["left", (x, y, z) => x === -1, `rotateY(-90deg) translateZ(${CUBIE / 2}px)`],
  ["top", (x, y, z) => y === -1, `rotateX(90deg) translateZ(${CUBIE / 2}px)`],
  ["bottom", (x, y, z) => y === 1, `rotateX(-90deg) translateZ(${CUBIE / 2}px)`],
];

function buildCube() {
  for (let x = -1; x <= 1; x += 1) {
    for (let y = -1; y <= 1; y += 1) {
      for (let z = -1; z <= 1; z += 1) {
        if (x === 0 && y === 0 && z === 0) continue;
        const cubie = document.createElement("div");
        cubie.className = "cubie";
        cubie.style.transform = `translate3d(${x * STEP}px, ${y * STEP}px, ${z * STEP}px)`;
        for (const [name, isOuter, transform] of FACES) {
          const face = document.createElement("div");
          face.className = `face ${name}`;
          face.style.transform = transform;
          if (isOuter(x, y, z)) {
            face.style.background = COLORS[name];
            face.style.boxShadow =
              "inset 0 0 16px rgba(255,255,255,.22), inset 0 -7px 14px rgba(0,0,0,.24)";
          } else {
            face.style.background = INNER;
            face.style.boxShadow = "none";
          }
          cubie.appendChild(face);
        }
        cube.appendChild(cubie);
      }
    }
  }
}

buildCube();

// ---------------------------------------------------------------------
// Animación del cubo
// ---------------------------------------------------------------------
let yaw = -0.55;
let targetYaw = yaw;
let spinning = false;
let lastFrame = performance.now();
const SPIN_SPEED = 1.55;

function tick(now) {
  const dt = Math.min((now - lastFrame) / 1000, 0.05);
  lastFrame = now;

  if (spinning) {
    yaw += SPIN_SPEED * dt;
    targetYaw = yaw;
  } else {
    const factor = Math.min(1, dt * 9.5);
    yaw += (targetYaw - yaw) * factor;
  }

  cube.style.transform = `rotateX(-22deg) rotateY(${yaw}rad)`;
  const bob = Math.sin(now / 1500) * 3.2;
  cubeScene.style.transform = `translateY(${bob}px)`;
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// ---------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------
const els = {
  cameraPill: document.getElementById("pill-camera"),
  cameraPillText: document.getElementById("camera-pill-text"),
  modelPill: document.getElementById("pill-model"),
  modelPillText: document.getElementById("model-pill-text"),
  fps: document.getElementById("fps-value"),
  cameraName: document.getElementById("camera-name"),
  handCount: document.getElementById("hand-count"),
  currentGesture: document.getElementById("current-gesture"),
  cameraHands: document.getElementById("camera-hands"),
  cameraFrame: document.querySelector(".camera-frame"),
  video: document.getElementById("video"),
  eventList: document.getElementById("event-list"),
  eventTime: document.getElementById("event-time"),
  stageLabel,
  overlay: document.getElementById("landmark-canvas"),
};
const overlayCtx = els.overlay.getContext("2d");

const ACTION_LABEL = {
  rotate_left: "Girar a la izquierda",
  rotate_right: "Girar a la derecha",
  spin_start: "Giro continuo",
  spin_stop: "Detener giro",
  reset: "Reset",
};
const GESTURE_LABEL = {
  idle: "—",
  fist: "PUÑO",
  open: "PALMA",
  unknown: "—",
  spin: "GIRANDO",
  rotate_left: "IZQUIERDA",
  rotate_right: "DERECHA",
  spin_start: "GIRANDO",
  spin_stop: "DETENIDO",
};
const HAND_LABEL = {
  Right: "Mano derecha",
  Left: "Mano izquierda",
  demo: "Demo",
  auto: "Automático",
};

let serverCamera = false;
let modelReady = false;
let gestureHoldUntil = 0;

function setPill(pill, state, text) {
  pill.classList.remove("on", "off", "warn");
  if (state) pill.classList.add(state);
  if (text !== undefined) {
    const b = pill.querySelector("b");
    if (b) b.textContent = text;
  }
}

function flashCard(card) {
  if (!card) return;
  gestureCards.forEach((c) => c.classList.remove("active", "fire"));
  void card.offsetWidth;
  card.classList.add("active", "fire");
  window.setTimeout(() => card.classList.remove("fire"), 780);
  window.setTimeout(() => card.classList.remove("active"), 1200);
}

function handleEvent(event) {
  if (!event) return;
  const action = event.action;
  const hand = event.hand;
  gestureHoldUntil = Date.now() + 1500;
  const hudLabel = {
    rotate_left: "IZQUIERDA",
    rotate_right: "DERECHA",
    spin_start: "GIRANDO",
    spin_stop: "DETENIDO",
    reset: "—",
  };
  els.currentGesture.textContent = hudLabel[action] || "—";

  if (action === "rotate_left") {
    targetYaw -= Math.PI / 2;
    flashCard(hand === "Left" ? document.getElementById("g-left-right") : document.getElementById("g-right-left"));
    stageLabel.textContent = "IZQUIERDA";
  } else if (action === "rotate_right") {
    targetYaw += Math.PI / 2;
    flashCard(hand === "Left" ? document.getElementById("g-left-right") : document.getElementById("g-right-left"));
    stageLabel.textContent = "DERECHA";
  } else if (action === "spin_start") {
    spinning = true;
    flashCard(document.getElementById("g-fist"));
    stageLabel.textContent = "GIRANDO";
  } else if (action === "spin_stop") {
    spinning = false;
    targetYaw = yaw;
    flashCard(document.getElementById("g-palm"));
    stageLabel.textContent = "DETENIDO";
  } else if (action === "reset") {
    spinning = false;
    spinActive = false;
    targetYaw = -0.55;
    stageLabel.textContent = "ACERCÁ LA MANO";
  }

  stageLabel.classList.remove("flash");
  void stageLabel.offsetWidth;
  stageLabel.classList.add("flash");
  addLog(event);
}

function addLog(event) {
  const empty = els.eventList.querySelector(".event-empty");
  if (empty) empty.remove();

  const item = document.createElement("div");
  item.className = "event-item";
  const color =
    event.action === "rotate_left" ? "var(--cyan)" :
    event.action === "rotate_right" ? "var(--pink)" :
    event.action === "spin_start" ? "var(--lime)" :
    event.action === "spin_stop" ? "var(--amber)" : "var(--muted)";
  const date = event.at ? new Date(event.at * 1000) : new Date();
  const time = date.toLocaleTimeString("es-AR", { hour12: false });

  item.innerHTML = `
    <span class="bar" style="background:${color}"></span>
    <span class="what">
      <b>${ACTION_LABEL[event.action] || event.action}</b>
      <span>${HAND_LABEL[event.hand] || event.hand || "—"}</span>
    </span>
    <time>${time}</time>
  `;
  els.eventList.prepend(item);
  while (els.eventList.children.length > 6) {
    els.eventList.lastElementChild.remove();
  }
  els.eventTime.textContent = time;
}

// ---------------------------------------------------------------------
// Detección de gestos (portado del motor Python)
// ---------------------------------------------------------------------
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];
const FINGER_TIPS = [8, 12, 16, 20];
const FINGER_PIPS = [6, 10, 14, 18];
const SWIPE_MIN_DX = 0.17;
const SWIPE_COOLDOWN_S = 0.90;
const SWIPE_MIN_SPEED = 0.32;
const STABLE_FRAMES = 4;

// La cámara de la placa se sirve espejada. MediaPipe etiqueta las manos
// sobre la imagen; invertimos la etiqueta para que "Right" sea la mano
// derecha real del visitante.
const MIRROR_HANDEDNESS = true;

const tracks = {
  Left: { samples: [], lastSeen: 0, cooldown: 0, stable: null, stableCount: 0 },
  Right: { samples: [], lastSeen: 0, cooldown: 0, stable: null, stableCount: 0 },
};
let spinActive = false;

function distance(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = (a.z || 0) - (b.z || 0);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

function countExtended(landmarks) {
  const wrist = landmarks[0];
  let count = 0;
  for (let i = 0; i < FINGER_TIPS.length; i += 1) {
    const dTip = distance(landmarks[FINGER_TIPS[i]], wrist);
    const dPip = distance(landmarks[FINGER_PIPS[i]], wrist);
    if (dPip > 1e-6 && dTip > dPip * 1.15) count += 1;
  }
  return count;
}

function classify(fingers) {
  if (fingers <= 1) return "fist";
  if (fingers >= 3) return "open";
  return "unknown";
}

function palmCenter(landmarks) {
  const ids = [0, 5, 9, 13, 17];
  let x = 0;
  let y = 0;
  for (const id of ids) {
    x += landmarks[id].x;
    y += landmarks[id].y;
  }
  return { x: x / ids.length, y: y / ids.length };
}

function emitGesture(rawAction, hand) {
  let action = rawAction;
  if (rawAction === "swipe_left") {
    action = hand === "Right" ? "rotate_left" : "rotate_right";
  } else if (rawAction === "swipe_right") {
    action = hand === "Right" ? "rotate_right" : "rotate_left";
  }
  handleEvent({ action, hand, at: Date.now() / 1000 });
}

function processHand(handedness, landmarks, palm, gesture, now) {
  const track = tracks[handedness];
  if (!track) return;
  track.lastSeen = now;
  track.samples.push({ t: now, x: palm.x, y: palm.y, gesture });
  if (track.samples.length > 48) track.samples.shift();

  if (gesture === "open" && now >= track.cooldown) {
    let reference = null;
    for (const sample of track.samples) {
      if (now - sample.t >= 0.45) reference = sample;
      else break;
    }
    if (reference) {
      const dt = Math.max(now - reference.t, 0.001);
      const dx = palm.x - reference.x;
      const dy = palm.y - reference.y;
      const speed = Math.abs(dx) / dt;
      if (
        Math.abs(dx) >= SWIPE_MIN_DX &&
        Math.abs(dx) >= Math.abs(dy) * 1.45 &&
        speed >= SWIPE_MIN_SPEED
      ) {
        const direction = dx < 0 ? "swipe_left" : "swipe_right";
        track.cooldown = now + SWIPE_COOLDOWN_S;
        track.samples.length = 0;
        emitGesture(direction, handedness);
      }
    }
  }

  if (gesture === track.stable) {
    track.stableCount += 1;
  } else {
    track.stable = gesture;
    track.stableCount = 1;
  }

  if (track.stableCount >= STABLE_FRAMES) {
    if (gesture === "fist" && handedness === "Right" && !spinActive) {
      spinActive = true;
      emitGesture("spin_start", handedness);
    } else if (gesture === "open" && spinActive) {
      spinActive = false;
      emitGesture("spin_stop", handedness);
    }
  }
}

function markHandMissing(handedness, now) {
  const track = tracks[handedness];
  if (!track) return;
  if (now - track.lastSeen > 0.6) {
    track.samples.length = 0;
    track.stable = null;
    track.stableCount = 0;
  }
  if (handedness === "Right" && spinActive && now - track.lastSeen > 1.2) {
    spinActive = false;
    emitGesture("spin_stop", "Right");
  }
}

function drawLandmarks(hands) {
  const w = els.overlay.width;
  const h = els.overlay.height;
  overlayCtx.clearRect(0, 0, w, h);

  for (const hand of hands) {
    const color = hand.handedness === "Right" ? "#00d4ff" : "#ff4fd8";
    const points = hand.landmarks.map((lm) => [lm.x * w, lm.y * h]);

    overlayCtx.lineWidth = 2.5;
    overlayCtx.strokeStyle = color;
    overlayCtx.shadowColor = color;
    overlayCtx.shadowBlur = 8;
    for (const [a, b] of HAND_CONNECTIONS) {
      if (!points[a] || !points[b]) continue;
      overlayCtx.beginPath();
      overlayCtx.moveTo(points[a][0], points[a][1]);
      overlayCtx.lineTo(points[b][0], points[b][1]);
      overlayCtx.stroke();
    }

    overlayCtx.shadowBlur = 0;
    for (const [x, y] of points) {
      overlayCtx.beginPath();
      overlayCtx.arc(x, y, 4, 0, Math.PI * 2);
      overlayCtx.fillStyle = "#ffffff";
      overlayCtx.fill();
      overlayCtx.lineWidth = 1.5;
      overlayCtx.strokeStyle = color;
      overlayCtx.stroke();
    }

    const label = `${hand.handedness.toUpperCase()} · ${hand.gesture.toUpperCase()}`;
    overlayCtx.font = "600 12px ui-monospace, monospace";
    const width = overlayCtx.measureText(label).width;
    overlayCtx.fillStyle = "rgba(3, 7, 13, 0.72)";
    overlayCtx.fillRect(12, 12, width + 16, 24);
    overlayCtx.fillStyle = color;
    overlayCtx.fillText(label, 20, 29);
  }
}

function updateHandHud(hands) {
  els.handCount.textContent = String(hands.length);
  els.cameraHands.textContent = `${hands.length} mano${hands.length === 1 ? "" : "s"}`;

  if (Date.now() < gestureHoldUntil) return;

  if (hands.length) {
    els.currentGesture.textContent = GESTURE_LABEL[hands[0].gesture] || "—";
    stageLabel.textContent = "ACERCÁ LA MANO";
  } else {
    els.currentGesture.textContent = spinning ? "GIRANDO" : "—";
    stageLabel.textContent = serverCamera ? "ACERCÁ LA MANO" : "CÁMARA NO DETECTADA";
  }
}

function processResult(result, now) {
  const landmarksList = result.landmarks || [];
  const handednessList = result.handednesses || result.handedness || [];
  const hands = [];
  const seen = new Set();

  for (let i = 0; i < landmarksList.length; i += 1) {
    let handedness = "Right";
    const categories = handednessList[i];
    if (categories && categories[0]) {
      handedness = categories[0].categoryName || "Right";
    }
    if (MIRROR_HANDEDNESS) {
      handedness = handedness === "Left" ? "Right" : "Left";
    }

    const landmarks = landmarksList[i];
    const palm = palmCenter(landmarks);
    const fingers = countExtended(landmarks);
    const gesture = classify(fingers);
    hands.push({ handedness, landmarks, palm, fingers, gesture });
    seen.add(handedness);
    processHand(handedness, landmarks, palm, gesture, now);
  }

  for (const handedness of ["Left", "Right"]) {
    if (!seen.has(handedness)) markHandMissing(handedness, now);
  }

  drawLandmarks(hands);
  updateHandHud(hands);
}

// ---------------------------------------------------------------------
// MediaPipe Tasks Vision
// ---------------------------------------------------------------------
let handLandmarker = null;

async function createLandmarker(vision, delegate) {
  return HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: "/static/models/hand_landmarker.task",
      delegate,
    },
    runningMode: "VIDEO",
    numHands: 2,
    minHandDetectionConfidence: 0.55,
    minHandPresenceConfidence: 0.55,
    minTrackingConfidence: 0.55,
  });
}

async function initMediaPipe() {
  setPill(els.modelPill, "warn", "CARGANDO");
  try {
    const vision = await FilesetResolver.forVisionTasks("/static/mediapipe/wasm");
    try {
      handLandmarker = await createLandmarker(vision, "GPU");
    } catch (gpuError) {
      console.warn("MediaPipe GPU no disponible; usando CPU", gpuError);
      handLandmarker = await createLandmarker(vision, "CPU");
    }
    modelReady = true;
    setPill(els.modelPill, "on", "LISTO");
  } catch (error) {
    console.error("No se pudo inicializar MediaPipe", error);
    modelReady = false;
    setPill(els.modelPill, "off", "ERROR");
    els.stageLabel.textContent = "MODELO NO DISPONIBLE";
  }
}

// ---------------------------------------------------------------------
// Loop de cámara + inferencia
// ---------------------------------------------------------------------
const workCanvas = document.createElement("canvas");
workCanvas.width = 640;
workCanvas.height = 480;
const workCtx = workCanvas.getContext("2d", { willReadFrequently: true });

let lastDetect = 0;
let detectCount = 0;
let detectWindowStart = performance.now();
let detectionErrorLogged = false;

function detectionLoop(now) {
  requestAnimationFrame(detectionLoop);

  if (!handLandmarker || !serverCamera) return;
  if (!els.video.complete || els.video.naturalWidth === 0) return;
  if (now - lastDetect < 66) return; // ~15 fps
  lastDetect = now;

  try {
    workCtx.drawImage(els.video, 0, 0, workCanvas.width, workCanvas.height);
    const result = handLandmarker.detectForVideo(workCanvas, now);
    detectCount += 1;
    if (now - detectWindowStart >= 1000) {
      const fps = (detectCount * 1000) / (now - detectWindowStart);
      els.fps.textContent = fps.toFixed(1);
      detectCount = 0;
      detectWindowStart = now;
    }
    processResult(result, now / 1000);
  } catch (error) {
    if (!detectionErrorLogged) {
      console.error("Error en la inferencia", error);
      detectionErrorLogged = true;
    }
  }
}
requestAnimationFrame(detectionLoop);

// ---------------------------------------------------------------------
// Estado del servidor (solo cámara y nombre del dispositivo)
// ---------------------------------------------------------------------
async function pollServerState() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) return;
    const state = await response.json();
    serverCamera = Boolean(state.camera);
    setPill(els.cameraPill, serverCamera ? "on" : "off", serverCamera ? "ONLINE" : "SIN SEÑAL");
    els.cameraName.textContent = state.camera_name || "buscando...";
    els.cameraFrame.classList.toggle("offline", !serverCamera);
    if (!serverCamera) {
      els.handCount.textContent = "0";
      els.cameraHands.textContent = "0 manos";
      if (Date.now() >= gestureHoldUntil) {
        els.currentGesture.textContent = spinning ? "GIRANDO" : "—";
        els.stageLabel.textContent = "CÁMARA NO DETECTADA";
      }
      overlayCtx.clearRect(0, 0, els.overlay.width, els.overlay.height);
    }
  } catch (_) {
    setPill(els.cameraPill, "off", "SIN CONEXIÓN");
  }
}
pollServerState();
window.setInterval(pollServerState, 1000);

// ---------------------------------------------------------------------
// Controles
// ---------------------------------------------------------------------
const DEMO_EVENTS = {
  right_swipe_left: { action: "rotate_left", hand: "Right" },
  left_swipe_right: { action: "rotate_left", hand: "Left" },
  right_fist: { action: "spin_start", hand: "Right" },
  open_palm: { action: "spin_stop", hand: "Right" },
  reset: { action: "reset", hand: "demo" },
};

document.querySelectorAll("[data-demo]").forEach((button) => {
  button.addEventListener("click", () => {
    const demo = DEMO_EVENTS[button.getAttribute("data-demo")];
    if (demo) handleEvent({ ...demo, at: Date.now() / 1000 });
  });
});

document.getElementById("fullscreen").addEventListener("click", async () => {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    } else {
      await document.exitFullscreen();
    }
  } catch (_) { /* ignorar */ }
});

window.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  const map = {
    "1": "right_swipe_left",
    "2": "left_swipe_right",
    "3": "right_fist",
    "4": "open_palm",
    "r": "reset",
  };
  if (map[key]) {
    const demo = DEMO_EVENTS[map[key]];
    if (demo) handleEvent({ ...demo, at: Date.now() / 1000 });
  } else if (key === "f") {
    document.getElementById("fullscreen").click();
  }
});

els.video.addEventListener("error", () => {
  els.cameraFrame.classList.add("offline");
});

initMediaPipe();
