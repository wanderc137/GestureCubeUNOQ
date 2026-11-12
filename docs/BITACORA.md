# Bitácora de desarrollo · GestureCube UNO Q

Registro de problemas, decisiones y lecciones del proyecto. No es un changelog: es la memoria técnica de por qué el código quedó como quedó, para no repetir errores en proyectos similares.

---

## 1. Contexto

**Objetivo:** un cubo Rubik 3D controlado por gestos de la mano, en vivo y 100 % offline, sobre Arduino UNO Q.

**Restricciones de origen:**

- La placa debe ser la única infraestructura en el puesto de feria (sin PC servidor).
- El visitante no debe instalar nada.
- Sin Internet: ni CDN, ni API keys, ni telemetría.
- La demo tiene que sobrevivir a desconexiones y reinicios sin intervención.

**Resultado:** arquitectura de captura en la placa e inferencia en el navegador. Software completo y auditado; cámara USB pendiente por un bloqueo físico del puerto USB-C.

---

## 2. Problemas encontrados y resolución

### 2.1 MediaPipe nativo aborta con `SIGILL`

**Síntoma:** al importar o inicializar MediaPipe en la UNO Q, el proceso muere con:

```text
FATAL ERROR: This binary was compiled with lse enabled, but this feature is not available on this processor
```

**Diagnóstico:** el Qualcomm QRB2210 es un ARMv8.0 Cortex-A53 sin extensión LSE (Large System Extensions). Los wheels aarch64 de MediaPipe 1.2.3 y 1.0.0 se compilaron con LSE habilitado; el loader acepta el binario pero la primera instrucción atómica lo mata.

**Resolución:** no se ejecuta MediaPipe nativo en la placa. La inferencia se movió al navegador con Tasks Vision (WASM/WebGL). `gesture_engine.py` quedó como referencia y respaldo para plataformas compatibles, importado con `try/except` para que el servicio no muera.

**Evidencia en el código:** `MEDIAPIPE_AVAILABLE`, `MEDIAPIPE_IMPORT_ERROR` y el mensaje de `model_error` en `app.py`.

### 2.2 Sin wheels de MediaPipe para Python 3.13 en aarch64

**Síntoma:** la placa trae Python 3.13.5; las versiones 0.10.x no publican wheels cp313 aarch64, y las 1.x que sí existen abortan por LSE (2.1).

**Resolución:** mismo pivote. Se evitó compilar desde fuente porque el costo (toolchain, dependencias, tiempo) no se justificaba para una demo que puede inferir en el cliente.

### 2.3 `matplotlib` como dependencia no deseada

**Síntoma:** `mediapipe` importa `matplotlib.pyplot` desde `drawing_utils`, aunque el proyecto no use funciones de dibujo. Instalar matplotlib en la placa sumaba peso y dependencias.

**Resolución:** en `gesture_engine.py`, si `matplotlib` no está, se inyectan módulos stub en `sys.modules` antes de importar MediaPipe. Es una solución acotada al motor de referencia; no afecta al navegador.

### 2.4 El escaneo de cámara elegía códecs internos

**Síntoma:** Linux expone nodos `/dev/videoN` que no son cámaras (por ejemplo, `qcom-venus-encoder` / `qcom-venus-decoder`). Abrirlos con OpenCV falla o entrega frames inválidos.

**Resolución:** `CameraWorker` lee `/sys/class/video4linux/videoN/name` y descarta nombres que contengan `venus`, `encoder`, `decoder` o `qcom`. Después prueba abrir y leer un frame real antes de aceptar el dispositivo.

**Lección:** en placas ARM con multimedia integrada, `/dev/video*` no implica cámara. Hay que validar por nombre y por lectura.

### 2.5 El único USB-C: cámara vs. cable de datos

**Síntoma:** la cámara USB no aparece; no hay `/dev/video*` de tipo UVC. El servicio publica el placeholder.

**Diagnóstico:** el puerto USB-C de la UNO Q estaba ocupado por el cable de datos a la PC. En modo dispositivo, ese puerto no puede hostear ni alimentar periféricos. No es un problema de driver ni de código.

**Resolución adoptada:** documentar el requisito de un **hub USB-C con Power Delivery** y agregar soporte de **cámara IP MJPEG** (`--camera http://IP:8080/video`) como alternativa que libera el puerto.

**Estado:** bloqueo físico pendiente. El software ya soporta ambas salidas; falta el hardware.

**Lección:** validar el mapa de puertos y modos del hardware **antes** de escribir el pipeline. Un solo puerto con doble función es una restricción de arquitectura, no un detalle.

### 2.6 La etiqueta de mano quedaba invertida

**Síntoma:** el motor clasificaba `Left` como `Right` y los barridos giraban al revés.

**Diagnóstico:** el servidor espeja el frame para que el visitante se vea como en un espejo. MediaPipe etiqueta la mano sobre la imagen que recibe, no sobre la escena real. Al espejar, la etiqueta se invierte.

**Resolución:** `MIRROR_HANDEDNESS = true` en `app.js`; se intercambian `Left` y `Right` después de leer el resultado. El motor Python no lo necesita porque, en su uso previsto, el frame no se espeja o la etiqueta se interpreta en el mismo espacio.

**Lección:** cualquier transformación geométrica del frame (flip, rotación, crop) debe aplicarse también a la semántica de las etiquetas.

### 2.7 MJPEG: streaming sin chunked

**Problema:** servir un stream infinito con HTTP/1.1 y `Content-Length` es imposible; con chunked, algunos clientes y proxies bufferizan.

**Resolución:** `protocol_version = "HTTP/1.0"` y `Connection: close` en `/video` y `/events`. Cada parte del multipart lleva su `Content-Length`. El cliente `<img>` se actualiza solo.

**Lección:** para MJPEG simple, HTTP/1.0 con `multipart/x-mixed-replace` es más robusto que pelear con chunked.

### 2.8 MIME de `.mjs` y `.wasm`

**Problema:** si el servidor entrega `vision_bundle.mjs` como `application/octet-stream`, el navegador rechaza el módulo ES; si entrega el `.wasm` con tipo incorrecto, `WebAssembly.instantiateStreaming` falla.

**Resolución:** `mimetypes.guess_type` en Python 3.13 resuelve `.mjs` como `text/javascript` y `.wasm` como `application/wasm`. El `.task` se sirve como binario, que es válido para `fetch`/modelo. Se verificó con `curl -I`.

**Lección:** probar la carga real en el navegador, no solo el `200` del `curl`.

### 2.9 systemd: permisos, `PYTHONPATH` y cámara

**Problema:** el servicio debe abrir `/dev/video*` sin root, importar dependencias desde `.pylibs/` y encontrar el proyecto aunque se copie en otra ruta.

**Resolución:**

- `User=arduino`, `Group=arduino`, `SupplementaryGroups=video`.
- `Environment=PYTHONPATH=.../.pylibs`.
- `WorkingDirectory` y `ExecStart` apuntan al wrapper `scripts/run-service.sh`.
- `install-service.sh` reemplaza la ruta `/home/arduino/GestureCubeUNOQ` por la ruta real antes de copiar la unidad.
- `Restart=always`, `RestartSec=5`, `TimeoutStopSec=10`.

**Lección:** la unidad no debe contener configuración local (cámara, puerto); eso va en `camera.env` y en el wrapper. Así la unidad es portable.

### 2.10 El servicio no debe morir si falta la cámara

**Problema:** en una feria, alguien desconecta la cámara o el hub. Si el proceso muere, la página deja de existir.

**Resolución:** `CameraWorker` reintenta cada 5 s, publica un placeholder generado con OpenCV y mantiene el servidor HTTP vivo. Si la cámara se cae a mitad de stream, libera, espera 2 s y reabre. `Restart=always` es la última red de seguridad.

**Lección:** en instalaciones desatendidas, la disponibilidad de la página es más importante que la disponibilidad perfecta del sensor.

### 2.11 La página debía mostrarse sin cámara

**Problema:** para probar el diseño y la demo en un stand sin cámara, hacía falta una forma de mover el cubo.

**Resolución:** botones y teclas que simulan eventos **en el cliente** (`DEMO_EVENTS` + `handleEvent`), sin depender del servidor. La API `/api/demo/*` quedó para automatización externa, pero no se usa en los botones.

**Lección:** separar "demo visual" de "pipeline de sensores" permite validar la UI y operar la feria aun con hardware incompleto.

### 2.12 SSE vs. polling

**Problema:** el servidor expone `/events` (SSE) con snapshots cada 250 ms, pero la página solo necesita saber si la cámara está online y su nombre.

**Decisión:** polling cada 1 s a `/api/state`. Es más simple, no mantiene una conexión abierta y alcanza para el HUD. SSE queda disponible para integraciones futuras.

**Lección:** no agregar complejidad de push cuando un GET periódico cubre el caso de uso.

### 2.13 Alcance del cubo

**Problema:** "cubo Rubik" puede implicar simulación de piezas, notación de movimientos y resolución.

**Decisión:** visualización de un cubo completo que gira en `yaw`; no hay estado de piezas ni resolución. Se documenta explícitamente para no prometer de más.

**Lección:** definir el alcance visual antes de elegir la tecnología; un cubo CSS de 26 cubies es suficiente para la metáfora.

---

## 3. Enfoques descartados

| Enfoque | Por qué se descartó |
|---|---|
| MediaPipe nativo en la UNO Q | `SIGILL` por LSE; wheels incompatibles con el CPU |
| Compilar MediaPipe desde fuente | Toolchain y tiempo desproporcionados para una demo; el navegador ya resuelve |
| MediaPipe 0.10.x | Sin wheels cp313 aarch64 |
| FastAPI/Flask en la placa | Dependencias y RAM extra; `http.server` cubre estáticos, MJPEG y JSON |
| WebRTC para el video | Señalización y complejidad innecesarias; MJPEG en `<img>` alcanza |
| Three.js para el cubo | Peso y superficie de error; CSS 3D es suficiente |
| CDN para el modelo/WASM | Rompe el offline y la privacidad |
| `venv` en la placa | El servicio usa `.pylibs` con `PYTHONPATH`; menos fricción en Debian de la UNO Q |
| Servir el video desde la PC | La placa debe ser autónoma en la feria |
| Autenticación en el panel | Demo de LAN; se documenta la limitación en lugar de agregar fricción |

---

## 4. Decisiones técnicas y justificación

| Decisión | Alternativa | Motivo |
|---|---|---|
| Inferencia en el navegador | Nativa en la placa | CPU sin LSE; mejor hardware en el cliente; privacidad |
| MJPEG sobre HTTP/1.0 | WebRTC/HLS | Simple, sin señalización, compatible con `<img>` |
| Servidor stdlib | FastAPI | Menos dependencias, RAM y arranque |
| Modelo y WASM vendorizados | CDN | Offline real y reproducible |
| Frame espejado en la placa | Espejar en CSS | Reflejo natural y overlay consistente |
| Invertir handedness en JS | No espejar | El espejo mejora la UX; la corrección es de una línea |
| Reglas geométricas | Clasificador adicional | Predecible, calibrable y sin otro modelo |
| Botones demo locales | Llamar a `/api/demo` | La UI funciona sin backend de eventos |
| Placeholder con OpenCV | Página vacía | Diagnóstico visual claro en la feria |
| `Restart=always` + reintentos | Solo systemd | Cubre fallos transitorios de cámara sin matar la página |

---

## 5. Lecciones aprendidas

1. **Validar el hardware antes que el software.** El bloqueo más costoso del proyecto no fue una red neuronal: fue un puerto USB-C con dos funciones incompatibles. Un diagrama de puertos y modos al inicio ahorra días.
2. **Probar los imports en el target real.** Un wheel que instala no es un wheel que corre. `SIGILL` en la primera instrucción es una lección sobre arquitecturas y flags de compilación.
3. **El offline se diseña, no se agrega al final.** Vendorizar runtime y modelo desde el principio evita refactors y garantiza la demo sin Internet.
4. **Las transformaciones de imagen afectan la semántica.** Flip, rotación o crop cambian etiquetas y coordenadas; hay que corregirlas en el mismo lugar donde se aplican.
5. **La página debe sobrevivir al sensor.** Separar la disponibilidad del servicio de la disponibilidad de la cámara es clave para una instalación desatendida.
6. **Documentar el estado real es parte del producto.** Una captura con `SIN SEÑAL` y una nota honesta valen más que un README que promete una cámara inexistente.
7. **La duplicación de lógica es deuda.** Tener el motor en JS y Python facilitó el pivote, pero hoy exige mantener umbrales sincronizados a mano. En el próximo proyecto, extraer una especificación de reglas compartida.
8. **Los botones de demo son infraestructura de feria.** Permiten validar la UI, capacitar operadores y seguir mostrando el proyecto cuando falla el hardware.
9. **HTTP/1.0 sigue siendo útil para MJPEG.** No hace falta un framework moderno para un stream de partes con `Content-Length`.
10. **El tamaño importa en la placa.** Evitar frameworks y dependencias innecesarias dejó un servicio que arranca rápido y se mantiene liviano.

---

## 6. Verificación de referencia

Chequeos usados para validar el servicio y revalidar el estado documentado:

```bash
python3 -m py_compile app.py gesture_engine.py
node --check static/app.js
curl -fsS http://127.0.0.1:8091/healthz
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8091/
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8091/static/mediapipe/vision_bundle.mjs
systemctl is-enabled gesturecube
systemctl is-active gesturecube
```

- El modelo carga en el navegador y el pill pasa a `LISTO`.
- La página responde y los estáticos se sirven con MIME correcto.
- El servicio arranca, se reinstala y sobrevive reinicios.
- La cámara no se detecta: bloqueo físico documentado.
- Los botones y teclas mueven el cubo sin cámara.

---

## 7. Pendientes y próximos pasos

1. **Hardware:** hub USB-C con PD + cámara UVC; validar `/dev/video*` y el stream en vivo.
2. **Alternativa:** probar una cámara IP MJPEG y dejar `camera.env` documentado para la feria.
3. **Calibración:** ajustar `SWIPE_MIN_DX` y `SWIPE_MIN_SPEED` con el público real.
4. **Tests:** extraer las reglas a un módulo testeable y cubrir landmarks sintéticos.
5. **Sincronización de motores:** unificar constantes JS/Python o generar el JS desde una especificación.
6. **UI:** selector de cámara y estado de reconexión más explícito.
7. **Documentación:** mantener la captura real actualizada cuando la cámara funcione.

---

## 8. Estado final

- **Software:** completo, documentado y auditado.
- **Servicio:** activo, con autoarranque y reintentos.
- **Inferencia:** funcionando en el navegador, offline.
- **Cámara:** pendiente por el puerto USB-C único; solución identificada (hub PD o cámara IP).
- **Honestidad:** el README, el datasheet y esta bitácora reflejan el mismo estado, sin métricas inventadas ni promesas de hardware.

---

*GestureCube · bitácora · licencia MIT © 2026 Jose Manuel Adasme.*
