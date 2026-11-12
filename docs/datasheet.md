# GestureCube · Datasheet de usuario

**Manual de operación para la demo de cubo Rubik 3D controlado por gestos sobre Arduino UNO Q.**

Versión del documento: 2.0 · Estado del proyecto: software funcional, cámara USB pendiente por el puerto USB-C único.

---

## 1. Descripción y alcance

GestureCube es una instalación de visión artificial para ferias y exhibiciones. Una cámara USB enfoca al visitante; la Arduino UNO Q captura el video y lo sirve por la red local como stream MJPEG. El navegador del visitante ejecuta MediaPipe Tasks Vision (WASM/WebGL) sobre ese video, detecta 21 puntos de la mano, interpreta el gesto y mueve un cubo Rubik 3D construido con CSS.

Este documento está pensado para quien **opera** la demo: armar el puesto, abrir el panel, explicar los gestos, resolver fallas típicas y apagar el equipo. La explicación del código está en [`developer.md`](developer.md) y los enlaces técnicos en [`REFERENCES.md`](REFERENCES.md).

**Alcance:**

- Operación en LAN, sin Internet.
- Un visitante por vez frente a la cámara (aunque el modelo detecta hasta dos manos).
- Visualización: el cubo gira, no se resuelve.
- Sin autenticación: red de confianza o hotspot dedicado.

---

## 2. Especificaciones técnicas

| Ítem | Valor |
|---|---|
| Plataforma | Arduino UNO Q (MPU Linux Qualcomm QRB2210, quad-core ARM Cortex-A53) |
| MCU auxiliar | STM32U585, **no usado** en este proyecto |
| Sistema | Debian 13 trixie, Python 3.13.5 |
| Cámara | USB UVC, 640×480, 30 fps solicitados |
| Entrada de cámara | Hub USB-C con Power Delivery o cámara IP MJPEG |
| Servicio | `gesturecube.service`, puerto `8091/tcp` |
| Inferencia | MediaPipe Tasks Vision 1.2.3 en el navegador (WASM, GPU→CPU) |
| Modelo | `hand_landmarker.task` float16, ~7,5 MB |
| Runtime web | `vision_bundle.mjs` + WASM, ~29 MB |
| Assets totales | ~37 MB |
| Dependencias Python | NumPy 2.2.6 + OpenCV contrib headless 4.12.0.88, ~55 MB |
| Red | LAN; no requiere Internet |
| Autenticación | Ninguna (demo) |
| Almacenamiento de video | Ninguno |
| Resolución del canvas | 640×480 |
| FPS de inferencia | ~15 fps |
| FPS de stream | 15 fps |
| Usuario del servicio | `arduino`, grupo suplementario `video` |
| Reinicio | `Restart=always`, `RestartSec=5` |

---

## 3. Requisitos y contenido

### Hardware

- Arduino UNO Q con Debian 13 y el proyecto instalado.
- Cámara USB UVC (Logitech Brio o webcam equivalente).
- Hub USB-C con alimentación externa (PD) y al menos un puerto USB-A.
- Fuente de alimentación para el hub.
- Router, switch o hotspot WiFi para la LAN.
- PC o teléfono con Chrome/Edge actualizado y WebGL.

### Software ya incluido en el proyecto

- `app.py`, `gesture_engine.py`, `static/`, `scripts/` y `systemd/`.
- Runtime y modelo de MediaPipe vendorizados en `static/`.
- `.pylibs/` con NumPy y OpenCV (no versionado; debe existir en la placa).

### No incluido

- Hub USB-C con PD.
- Cámara.
- Cable de red.
- Fuente del hub.

---

## 4. Puesta en marcha rápida

1. Conectar el hub USB-C con PD al puerto USB-C de la UNO Q.
2. Conectar la cámara USB al hub y la fuente al hub.
3. Verificar que el servicio esté activo:

   ```bash
   systemctl is-active gesturecube
   curl -s http://127.0.0.1:8091/healthz
   ```

4. Abrir el panel desde la PC o el teléfono:

   - Directo: `http://192.168.10.75:8091/`
   - Vía router demo: `http://192.168.10.1:8091/`

5. Esperar a que el pill **MODELO** diga `LISTO`. Si la cámara está bien, **CÁMARA** dirá `ONLINE`.
6. Pararse a 1–2 m, con luz frontal, y probar un barrido.

Si la cámara no aparece, el panel sigue siendo usable con los botones del pie. Ver la sección 10.

---

## 5. Operación

### 5.1 Antes de la feria

- [ ] Hub PD conectado y alimentado.
- [ ] Cámara visible: `ls -l /dev/video*` y `cat /sys/class/video4linux/video*/name`.
- [ ] Servicio activo y `healthz` con `ok: true`.
- [ ] Panel abierto en la PC de control y en un teléfono.
- [ ] `MODELO LISTO` en ambos.
- [ ] Luz frontal; sin ventanas ni focos a contraluz.
- [ ] Cubo a una altura cómoda para la mano.
- [ ] Botones de demo probados.
- [ ] Pantalla completa activada (`f`).

### 5.2 Durante la demo

1. El visitante se ubica a 1–2 m de la cámara.
2. Apoya la mano abierta dentro del cuadro hasta ver el esqueleto.
3. Hace un barrido horizontal rápido: el cubo gira 90°.
4. Cierra el puño derecho y lo mantiene: el cubo gira continuo.
5. Abre la palma: el giro se detiene.
6. Si hay dos personas, que solo una haga gestos por vez.

### 5.3 Después de la feria

```bash
sudo systemctl stop gesturecube
```

El servicio queda `enabled` para el próximo arranque. No hace falta desinstalarlo. Si se quiere evitar el autoarranque:

```bash
sudo systemctl disable gesturecube
```

---

## 6. Gestos

| Gesto | Mano | Acción | Efecto |
|---|---|---|---|
| Barrido derecha → izquierda | Derecha | `rotate_left` | Gira 90° a la izquierda |
| Barrido izquierda → derecha | Izquierda | `rotate_left` | Gira 90° a la izquierda |
| Barrido izquierda → derecha | Derecha | `rotate_right` | Gira 90° a la derecha |
| Barrido derecha → izquierda | Izquierda | `rotate_right` | Gira 90° a la derecha |
| Puño cerrado sostenido | Derecha | `spin_start` | Giro continuo |
| Palma abierta | Cualquiera | `spin_stop` | Detiene el giro |
| Mano fuera de cuadro | — | `spin_stop` | Corta a los ~1,2 s |

### 6.1 Cómo se detecta

- **Dedos extendidos:** se compara la distancia muñeca→punta contra muñeca→articulación PIP. Si la punta está >15 % más lejos, el dedo está extendido. El pulgar no se cuenta.
- **Puño:** 1 o menos dedos extendidos, sostenido 4 frames.
- **Palma:** 3 o más dedos extendidos, sostenida 4 frames.
- **Barrido:** ventana de ~0,45 s; desplazamiento horizontal ≥17 % del ancho; componente horizontal >1,45× la vertical; velocidad ≥0,32/s; cooldown 0,9 s.
- **Giro:** solo lo inicia el puño derecho. La palma lo detiene. Si la mano desaparece, se corta solo.

### 6.2 Consejos para que funcione bien

- Mano completamente visible, no a medio cuadro.
- Luz frontal y pareja; evitar contraluz.
- Barrido rápido y horizontal; los movimientos lentos no alcanzan la velocidad mínima.
- Una mano por gesto.
- No tapar la cámara con el cuerpo.
- Si el visitante es niño o persona mayor, el operador puede bajar los umbrales (ver `developer.md`).

### 6.3 Qué significa "girar"

El cubo entero gira alrededor del eje vertical. No se mueven caras individuales ni se guarda el estado de las piezas. Es una visualización para la demo, no un solucionador de cubos.

---

## 7. Interfaz e indicadores

### 7.1 Barra superior

| Indicador | Estados | Significado |
|---|---|---|
| **CÁMARA** | `ONLINE` | La placa recibe frames |
| | `SIN SEÑAL` | No hay cámara UVC o el hub no está conectado |
| | `SIN CONEXIÓN` | Falló el polling a `/api/state` |
| **MODELO** | `CARGANDO` | El navegador está inicializando MediaPipe |
| | `LISTO` | Modelo y WASM cargados |
| | `ERROR` | Falló la carga; revisar consola y rutas |
| **FPS** | número | FPS de inferencia del navegador |

### 7.2 Panel izquierdo

- Cuatro tarjetas de gestos; se iluminan cuando la regla se dispara.
- Nota "Análisis local con MediaPipe. Nada sale de la placa."

### 7.3 Escenario central

- Cubo Rubik 3D con 26 cubies, sombra y flotación.
- Etiqueta de estado: `ACERCÁ LA MANO`, `CÁMARA NO DETECTADA`, `IZQUIERDA`, `DERECHA`, `GIRANDO`, `DETENIDO`.
- HUD: **MANOS**, **GESTO**, **MODO: OFFLINE**.

### 7.4 Panel derecho

- Video de la cámara con overlay de landmarks.
- Badge `LIVE` y contador de manos.
- Último gesto con hora, acción y mano.
- Resolución (640×480) e inferencia (`LOCAL`).

### 7.5 Pie

- Botones de prueba y pista de gestos.
- Botón de pantalla completa.

---

## 8. Controles de prueba

Los botones simulan eventos en el navegador, sin pasar por el servidor.

| Botón | Efecto |
|---|---|
| `← der.` | Barrido de mano derecha; gira a la izquierda |
| `izq. →` | Barrido de mano izquierda; gira a la izquierda |
| `puño` | Inicia giro continuo |
| `palma` | Detiene el giro |
| `reset` | Vuelve a la orientación inicial |

| Tecla | Acción |
|---|---|
| `1` | Barrido derecho → izquierda |
| `2` | Barrido izquierdo → derecha |
| `3` | Puño / giro continuo |
| `4` | Palma / detener |
| `r` | Reset |
| `f` | Pantalla completa |

Estos controles permiten mostrar la página aunque no haya cámara. Si se quiere disparar un gesto desde otro programa, usar la API `POST /api/demo/<acción>`.

---

## 9. API para operadores

| Ruta | Método | Uso |
|---|---|---|
| `/` | GET | Panel |
| `/video` | GET | Stream MJPEG |
| `/api/state` | GET | Estado completo |
| `/healthz` | GET | Chequeo rápido |
| `/api/demo/<acción>` | POST | Evento de prueba |
| `/api/reset` | POST | Reset |

```bash
curl -s http://127.0.0.1:8091/healthz | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8091/api/demo/right_fist
curl -s -X POST http://127.0.0.1:8091/api/reset
```

Acciones de demo: `right_swipe_left`, `right_swipe_right`, `left_swipe_right`, `left_swipe_left`, `right_fist`, `open_palm`, `spin_stop`, `reset`.

`/healthz` devuelve `model: false` porque el motor nativo de Python está deshabilitado a propósito; `browser_model: true` indica que el modelo para el navegador está presente.

---

## 10. Configuración

### 10.1 `camera.env`

Archivo local en la raíz del proyecto, no versionado:

```bash
GESTURECUBE_CAMERA=http://192.168.10.249:8080/video
# GESTURECUBE_CAMERA=/dev/video2
# GESTURECUBE_PORT=8091
```

`scripts/run-service.sh` lo carga antes de ejecutar `app.py`. Después de cambiarlo:

```bash
sudo systemctl restart gesturecube
```

### 10.2 Argumentos manuales

```bash
PYTHONPATH=.pylibs python3 app.py \
  --host 0.0.0.0 --port 8091 \
  --camera /dev/video2
```

| Argumento | Efecto |
|---|---|
| `--camera` | Dispositivo o URL MJPEG |
| `--no-mirror` | Desactiva el espejado |
| `--debug` | Logs detallados |
| `--host` / `--port` | Interfaz y puerto |

### 10.3 Prioridad

1. Argumentos de línea de comandos.
2. Variables de entorno.
3. Defaults del código: `0.0.0.0`, `8091`, escaneo de `/dev/video*`.

---

## 11. Dependencias

Las librerías del servidor están declaradas en [`requirements.txt`](../requirements.txt):

| Librería | Versión | Rol |
|---|---|---|
| `numpy` | 2.2.6 | Operaciones numéricas y manejo de frames |
| `opencv-contrib-python-headless` | 4.12.0.88 | Captura V4L2, espejado, JPEG y placeholder |

### 11.1 Instalación en un entorno virtual del proyecto

Para desarrollo o para correr el servidor en un Linux de escritorio:

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

Con el entorno activo:

```bash
python app.py --host 0.0.0.0 --port 8091
```

### 11.2 Instalación en la UNO Q

En la placa **no se usa `venv`**: las dependencias viven en `.pylibs/` y el servicio apunta `PYTHONPATH` ahí. Se instalaron con wheels aarch64:

```bash
python3 pip-26.3-py3-none-any.whl install \
  --target=.pylibs --no-deps \
  numpy-2.2.6-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl \
  opencv_contrib_python_headless-4.12.0.88-cp37-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl
```

- **No instalar MediaPipe nativo en la UNO Q:** el CPU QRB2210 no soporta LSE y los wheels 1.x abortan con `SIGILL`.
- La inferencia de manos corre en el navegador; no es una dependencia de la placa.
- `.pylibs/` está en `.gitignore`; si se borra, el servicio no arranca.
- El modelo y el runtime web **sí** están versionados en `static/`.

### 11.3 Comprobación

```bash
PYTHONPATH=.pylibs python3 -c "import numpy, cv2; print(numpy.__version__, cv2.__version__)"
```

Salida esperada:

```text
2.2.6 4.12.0
```

---

## 12. Mantenimiento

| Tarea | Comando |
|---|---|
| Estado | `systemctl status gesturecube` |
| Logs en vivo | `journalctl -u gesturecube -f` |
| Reiniciar | `sudo systemctl restart gesturecube` |
| Detener | `sudo systemctl stop gesturecube` |
| Health check | `curl http://127.0.0.1:8091/healthz` |
| Diagnóstico | `./scripts/status.sh` |
| Reinstalar unidad | `sudo ./scripts/install-service.sh` |

### Actualizar el software

1. Copiar `app.py`, `static/`, `scripts/` y `systemd/` al directorio de la placa.
2. Si cambió la unidad: `sudo ./scripts/install-service.sh`.
3. Si no: `sudo systemctl restart gesturecube`.
4. Verificar `healthz` y abrir el panel con caché limpia (`Ctrl+F5`).

### No borrar

- `.pylibs/`: NumPy y OpenCV.
- `static/mediapipe/`: runtime WASM.
- `static/models/hand_landmarker.task`: modelo.
- `camera.env`: configuración local de cámara.

---

## 13. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `CÁMARA SIN SEÑAL` | USB-C ocupado por cable de datos; hub sin PD | Conectar hub con PD y cámara al hub; liberar el puerto |
| Solo aparece `qcom-venus-*` | No hay cámara UVC; son códecs internos | Conectar una cámara UVC real |
| `MODELO CARGANDO` eterno | Primera carga lenta o recurso faltante | Esperar, revisar consola y `/static/...` |
| `MODELO ERROR` | WASM/modelo incompletos o WebGL bloqueado | Revisar rutas, probar otro navegador |
| El cubo no gira | Gesto lento, mano fuera de cuadro, poca luz | Barrido rápido, mano completa, luz frontal |
| El giro no se detiene | Palma no detectada | Abrir bien la mano 4 frames; botón `palma` |
| Video negro | Primer frame demorado o sin cámara | Probar `/video`; revisar logs |
| Servicio caído | Falta `.pylibs`, puerto ocupado, permisos | `journalctl`, `ss -ltnp`, revisar `.pylibs` |
| `Permission denied` en `/dev/video0` | Usuario fuera del grupo `video` | Usar la unidad (ya incluye el grupo) o `sudo` |
| Página sin conexión | IP cambiada o servicio detenido | Verificar IP y `systemctl status` |
| Cámara IP no abre | URL no MJPEG, ruta o auth | Probar en VLC; usar MJPEG HTTP sin auth |

### Diagnóstico rápido de cámara

```bash
ls -l /dev/video*
cat /sys/class/video4linux/video*/name
journalctl -u gesturecube -n 50
PYTHONPATH=.pylibs python3 -c "import cv2; c=cv2.VideoCapture(0); print(c.isOpened()); ok,f=c.read(); print(ok, None if not ok else f.shape)"
```

### Diagnóstico rápido del servicio

```bash
systemctl status gesturecube
ss -ltnp | grep 8091
curl -v http://127.0.0.1:8091/healthz
```

---

## 14. Advertencias y límites

- **El puerto USB-C es único.** No se puede usar la cámara y el cable de datos a la PC al mismo tiempo sin un hub con PD.
- **No exponer el panel a Internet.** No hay autenticación ni TLS.
- **El cubo no resuelve un Rubik.** Es una visualización; no mantiene estado de piezas.
- **La inferencia depende del navegador.** Probar la PC o el teléfono de la feria antes de abrir.
- **No hay grabación.** El video no se almacena; el feed de gestos se pierde al recargar.
- **El motor nativo Python no corre en esta placa.** Queda como referencia para plataformas compatibles.
- **Los assets son de terceros.** MediaPipe Apache 2.0, OpenCV Apache 2.0, NumPy BSD.
- **Avisar que hay una cámara.** En una feria, informar para qué se usa y no grabar personas sin consentimiento.

---

## 15. Preguntas frecuentes

**¿Necesita Internet?** No. El modelo, el WASM y la página se sirven desde la placa. Solo se necesita LAN entre el visitante y la UNO Q.

**¿Se puede usar sin cámara?** Sí, con los botones del pie o las teclas `1`–`4`. La página y el cubo funcionan; el video muestra `SIN SEÑAL`.

**¿Por qué la cámara no aparece?** Porque el único USB-C está ocupado por el cable de datos o el hub no tiene alimentación. Ver sección 10 y el README.

**¿Cuántas manos detecta?** Hasta dos, pero la demo está pensada para una. Dos manos pueden confundir la etiqueta y disparar gestos cruzados.

**¿Se puede ver desde el teléfono?** Sí, en la misma LAN, con Chrome/Edge actualizado. La inferencia corre en el teléfono.

**¿Se guarda el video?** No. No hay grabación ni historial persistente.

**¿Se puede cambiar el color o el tamaño del cubo?** Sí; los colores están en `static/app.js` (`COLORS`) y el tamaño en `--cubie` / `--step` de `style.css`.

**¿Se puede agregar otro gesto?** Sí; ver la guía de extensión en `developer.md`. Hay que tocar el motor JS y, si se quiere mantener paridad, el Python.

**¿Qué pasa si se cae la red?** El panel deja de actualizar y el MJPEG se corta. Al volver la red, recargar la página. El servicio de la placa sigue corriendo.

**¿Qué pasa si se desconecta la cámara?** El servicio sigue vivo, publica el placeholder y reintenta cada 5 s. Al reconectar, vuelve solo.

---

## 16. Glosario

| Término | Significado |
|---|---|
| UVC | USB Video Class; estándar de cámaras USB sin driver propietario |
| V4L2 | Video4Linux2; API de video del kernel Linux |
| MJPEG | Motion JPEG; secuencia de imágenes JPEG |
| Landmark | Punto de referencia de la mano (21 por mano) |
| WASM | WebAssembly; formato binario ejecutable en el navegador |
| WebGL | API de gráficos 3D del navegador |
| `rotate_left` / `rotate_right` | Acción de girar el cubo 90° |
| `spin_start` / `spin_stop` | Iniciar/detener el giro continuo |
| Hub PD | Hub USB-C con Power Delivery y alimentación externa |
| `.pylibs` | Carpeta local con las dependencias Python de la placa |

---

*GestureCube · Arduino UNO Q · documentación de usuario · licencia MIT © 2026 Jose Manuel Adasme.*
