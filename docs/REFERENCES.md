# Referencias · GestureCube UNO Q

Lista comentada de documentación, especificaciones y recursos usados para construir y operar el proyecto. Cada entrada indica **qué es** y **para qué sirve** en este repositorio.

> Todos los enlaces son externos y pueden cambiar. La documentación local (`README.md`, `datasheet.md`, `developer.md`) es la fuente de verdad para el comportamiento implementado.

---

## 1. MediaPipe y visión artificial

### [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)

Página oficial del modelo de 21 landmarks. Define los puntos de la mano (muñeca, dedos, puntas), las opciones de configuración (`numHands`, confidencias), los modos de ejecución (`IMAGE`, `VIDEO`, `LIVE_STREAM`) y los modelos disponibles.

**Uso en el proyecto:** es la referencia del contrato de datos que consume `static/app.js` y `gesture_engine.py`. Los índices 0, 5, 9, 13, 17 para la palma y 8/12/16/20 para las puntas salen de acá.

### [Hand Landmarker · Web/JavaScript](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/web_js)

Guía de la API web: `FilesetResolver.forVisionTasks()`, `HandLandmarker.createFromOptions()`, `detectForVideo()`, delegate GPU/CPU y carga del modelo.

**Uso en el proyecto:** implementación de `initMediaPipe()` y del loop de inferencia en `static/app.js`.

### [MediaPipe Solutions Guide](https://ai.google.dev/edge/mediapipe/solutions/guide)

Panorama de Tasks Vision: tareas disponibles, plataformas (Android, iOS, Python, Web), formato de modelos `.task` y conceptos de `BaseOptions`.

**Uso en el proyecto:** justifica la elección de Tasks Vision sobre la API legacy `mediapipe.solutions`, que no está disponible en MediaPipe 1.2.x.

### [Hand Landmarker · modelos y model card](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker#models)

Sección donde se publican los modelos float16/float32, sus tamaños y la model card con detalles de entrenamiento, métricas y limitaciones.

**Uso en el proyecto:** origen del archivo `static/models/hand_landmarker.task` (variante float16, ~7,5 MB) y contexto para entender sus límites.

### [Modelo Hand Landmarker float16 (archivo)](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task)

URL directa del artefacto que se vendorizó. Se sirve localmente para que la página funcione sin Internet.

**Uso en el proyecto:** `static/models/hand_landmarker.task`; `static/models/README.md` conserva la procedencia.

### [MediaPipe en GitHub](https://github.com/google-ai-edge/mediapipe)

Código fuente, issues, releases y notas de compatibilidad. Útil para verificar por qué una versión no tiene wheels para cierta combinación de Python/arquitectura.

**Uso en el proyecto:** diagnóstico de la ausencia de wheels cp313 aarch64 en 0.10.x y de los requisitos de LSE en 1.x.

### [Model card de hand tracking (PDF oficial)](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20(Lite_Full)%20with%20Fairness%20Oct%202021.pdf)

Model card enlazada por la página oficial de Hand Landmarker. Describe el modelo base de hand tracking (Lite/Full), los datasets y las consideraciones de fairness de 2021. No es la ficha técnica del `.task` actual, pero es la referencia oficial disponible sobre el linaje del modelo.

**Uso en el proyecto:** contexto para entender límites y sesgos del detector; no se usa en runtime.

### [@mediapipe/tasks-vision en npm](https://www.npmjs.com/package/@mediapipe/tasks-vision)

Paquete del runtime web. Lista versiones, dependencias y archivos publicados.

**Uso en el proyecto:** `static/mediapipe/vision_bundle.mjs` corresponde a la versión 1.2.3, vendorizada sin modificaciones.

### [MediaPipe releases](https://github.com/google-ai-edge/mediapipe/releases)

Historial de versiones y cambios de compatibilidad. Permite evaluar si una versión futura resuelve el soporte aarch64/Python 3.13.

**Uso en el proyecto:** referencia para futuras actualizaciones del runtime o del modelo.

---

## 2. WebAssembly, WebGL y web

### [WebAssembly](https://webassembly.org/)

Sitio oficial del formato: modelo de ejecución, módulos, memoria lineal e integración con JavaScript.

**Uso en el proyecto:** explica por qué el runtime de MediaPipe puede correr en el navegador sin plugins y con rendimiento cercano al nativo.

### [MDN · WebAssembly](https://developer.mozilla.org/en-US/docs/WebAssembly)

Guía práctica de WebAssembly: conceptos, carga de módulos, interoperabilidad con JS y depuración.

**Uso en el proyecto:** contexto para entender `vision_wasm_internal.wasm` y `vision_wasm_module_internal.wasm`.

### [MDN · WebGL API](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API)

Documentación de WebGL: contexto, shaders, texturas y limitaciones. Es la API que usa el delegate GPU de MediaPipe.

**Uso en el proyecto:** `delegate: "GPU"` en `createLandmarker()`, con fallback a `"CPU"` si el navegador no puede crear el contexto.

### [Khronos · WebGL](https://www.khronos.org/webgl/)

Especificación y recursos oficiales de WebGL.

**Uso en el proyecto:** referencia de compatibilidad para navegadores de feria.

### [MDN · `transform-style`](https://developer.mozilla.org/en-US/docs/Web/CSS/transform-style)

Propiedad que preserva el espacio 3D de los hijos. Sin `preserve-3d`, las caras del cubo se aplanan.

**Uso en el proyecto:** `.cube` y `.cubie` en `static/style.css`.

### [MDN · `perspective`](https://developer.mozilla.org/en-US/docs/Web/CSS/perspective)

Define la profundidad de la escena 3D. Es lo que da volumen al cubo.

**Uso en el proyecto:** `.cube-scene` / `.cube` en `static/style.css`.

### [MDN · `requestAnimationFrame`](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame)

Loop de animación sincronizado con el refresco del navegador.

**Uso en el proyecto:** `tick()` para el `yaw` del cubo y `detectionLoop()` para la inferencia.

### [MDN · `EventSource`](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)

API de Server-Sent Events. El servidor expone `/events`, aunque la página actual usa polling.

**Uso en el proyecto:** alternativa documentada para consumir el estado sin polling.

---

## 3. Captura y video

### [OpenCV · `VideoCapture`](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html)

Clase de captura: constructores, `isOpened()`, `read()`, `set()` de propiedades, `release()`.

**Uso en el proyecto:** `CameraWorker._try_capture()` y el loop de captura en `app.py`.

### [OpenCV · Video I/O con Python](https://docs.opencv.org/4.x/dd/d43/tutorial_py_video_display.html)

Tutorial de lectura/escritura de video y uso básico de `VideoCapture`.

**Uso en el proyecto:** base del código de captura y de la prueba manual con `cv2.VideoCapture(0)`.

### [V4L2 · kernel documentation](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html)

API de Video4Linux2: dispositivos, buffers, formatos y controles.

**Uso en el proyecto:** `/dev/videoN`, `CAP_V4L2` y la lectura de `/sys/class/video4linux/videoN/name`.

### [uvcvideo · kernel documentation](https://www.kernel.org/doc/html/latest/userspace-api/media/drivers/uvcvideo.html)

Driver de cámaras USB Video Class en Linux.

**Uso en el proyecto:** explica por qué una cámara UVC aparece como `/dev/videoN` y por qué los nodos `qcom-venus-*` no son cámaras.

### [Motion JPEG · Wikipedia](https://en.wikipedia.org/wiki/Motion_JPEG)

Descripción del formato MJPEG: secuencia de JPEG, usos y latencia.

**Uso en el proyecto:** formato del stream `/video` y del JPEG q=82 que publica la placa.

### [RFC 2046 · Multipart](https://www.rfc-editor.org/rfc/rfc2046)

Especificación de `multipart/*`, base de `multipart/x-mixed-replace`.

**Uso en el proyecto:** estructura `--frame`, `Content-Type`, `Content-Length` del stream MJPEG.

### [MDN · Tipos MIME](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/MIME_types)

Tipos de contenido y su relación con la ejecución de módulos y WASM en el navegador.

**Uso en el proyecto:** `mimetypes.guess_type` en `Handler._serve_file()`; `.mjs` y `.wasm` deben servirse con el tipo correcto.

---

## 4. Hardware y sistema

### [Arduino UNO Q · documentación](https://docs.arduino.cc/hardware/uno-q)

Especificaciones oficiales, arquitectura de doble cerebro (MPU Linux + MCU), pines, alimentación y puesta en marcha.

**Uso en el proyecto:** plataforma, Debian 13, puerto USB-C único y recomendación de hub con Power Delivery.

### [Arduino UNO Q · producto](https://store.arduino.cc/products/uno-q)

Descripción comercial, contenidos y accesorios.

**Uso en el proyecto:** contexto de hardware para el README y el datasheet.

### [Debian 13 trixie](https://www.debian.org/releases/trixie/)

Notas de la release usada por la UNO Q.

**Uso en el proyecto:** base del sistema, Python 3.13 y paquetes disponibles.

### [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)

Directivas de unidad: `Type`, `ExecStart`, `Restart`, `RestartSec`, `TimeoutStopSec`, `WorkingDirectory`.

**Uso en el proyecto:** `systemd/gesturecube.service`.

### [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)

Usuario, grupo, `SupplementaryGroups`, variables de entorno y directorio de trabajo.

**Uso en el proyecto:** `User=arduino`, `Group=arduino`, `SupplementaryGroups=video`, `PYTHONPATH`.

### [journalctl](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html)

Consulta de logs del servicio.

**Uso en el proyecto:** `journalctl -u gesturecube -f` para diagnóstico.

### [Python · `http.server`](https://docs.python.org/3/library/http.server.html)

`HTTPServer`, `ThreadingHTTPServer`, `BaseHTTPRequestHandler`. Documenta el modelo de hilos y el manejo de requests.

**Uso en el proyecto:** servidor completo en `app.py`, sin frameworks.

---

## 5. Python y dependencias

### [NumPy](https://numpy.org/doc/stable/)

Documentación de arrays, operaciones y `np.linalg.norm`.

**Uso en el proyecto:** frame placeholder, conversión BGR→RGB y distancias en `gesture_engine.py`.

### [OpenCV](https://opencv.org/)

Sitio oficial: módulos, releases y licencia Apache 2.0.

**Uso en el proyecto:** captura, espejado, `imencode`, dibujo de overlay y placeholder.

### [pip · `--target`](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-t)

Instalación de paquetes en un directorio específico, sin tocar el entorno del sistema.

**Uso en el proyecto:** `.pylibs/` en la UNO Q.

### [Python · `venv`](https://docs.python.org/3/library/venv.html)

Entornos virtuales para desarrollo y reproducción en escritorio.

**Uso en el proyecto:** bloque de instalación de `requirements.txt` documentado en README y datasheet.

### [Python · `mimetypes`](https://docs.python.org/3/library/mimetypes.html)

Resolución de tipos MIME por extensión.

**Uso en el proyecto:** `_serve_file()` para `.mjs`, `.wasm`, `.task`, CSS y JS.

### [Python · `threading`](https://docs.python.org/3/library/threading.html)

Hilos, locks y eventos.

**Uso en el proyecto:** `CameraWorker`, `AppState.lock`, `stop_event`, `ThreadingHTTPServer`.

### [Python · `argparse`](https://docs.python.org/3/library/argparse.html)

Parseo de argumentos de línea de comandos.

**Uso en el proyecto:** `--host`, `--port`, `--camera`, `--model`, `--no-mirror`, `--debug`.

### [GCC · AArch64 options](https://gcc.gnu.org/onlinedocs/gcc/AArch64-Options.html)

Opciones de compilación para AArch64, incluido el manejo de atomics y LSE.

**Uso en el proyecto:** contexto del error `This binary was compiled with lse enabled` y de la decisión de no compilar MediaPipe en la placa.

---

## 6. Alternativas evaluadas

### [FastAPI](https://fastapi.tiangolo.com/)

Framework ASGI con validación y documentación automática.

**Uso en el proyecto:** **evaluado y descartado** para la placa. El servidor necesita servir estáticos, MJPEG y JSON; `http.server` cubre eso con menos dependencias y menos RAM. Se documenta para que la decisión sea explícita.

### [Three.js](https://threejs.org/)

Librería 3D para WebGL.

**Uso en el proyecto:** **descartada** para el cubo. 26 cubies y transformaciones CSS alcanzan para la visualización, con menos peso y menos superficie de error. No se carga en runtime.

### [WebRTC](https://webrtc.org/)

Protocolo de video en tiempo real con baja latencia.

**Uso en el proyecto:** **descartado** para el transporte. Requiere señalización y más complejidad; MJPEG en `<img>` es suficiente para gestos y funciona en cualquier navegador.

---

## 7. Documentación local

| Archivo | Contenido |
|---|---|
| [`README.md`](../README.md) | Visión general, arquitectura, instalación, operación y referencias |
| [`datasheet.md`](datasheet.md) | Manual de usuario, especificaciones, dependencias y troubleshooting |
| [`developer.md`](developer.md) | Arquitectura de código, módulos, contratos y guía de extensión |
| [`BITACORA.md`](BITACORA.md) | Problemas, decisiones y lecciones del desarrollo |
| [`../static/mediapipe/README.md`](../static/mediapipe/README.md) | Origen y licencia del runtime vendorizado |
| [`../static/models/README.md`](../static/models/README.md) | Origen y licencia del modelo |
| [`../LICENSE`](../LICENSE) | Licencia MIT del proyecto |

---

## 8. Cómo mantener esta lista

- Agregar solo enlaces que se hayan usado o evaluado realmente.
- Indicar siempre **para qué** sirve el recurso en este proyecto.
- Si un enlace deja de existir, reemplazarlo por la fuente oficial vigente y anotar el cambio en `BITACORA.md`.
- No incluir enlaces a binarios, modelos o assets que no estén versionados o documentados en el repositorio.

---

*GestureCube · referencias · licencia MIT © 2026 Jose Manuel Adasme.*
