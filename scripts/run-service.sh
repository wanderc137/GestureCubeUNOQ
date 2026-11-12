#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -d "$PROJECT_DIR/.pylibs" ]]; then
  echo "Falta $PROJECT_DIR/.pylibs. Instalá las dependencias primero." >&2
  exit 1
fi

# Configuración local opcional (no versionada).
# Ejemplo de camera.env:
#   GESTURECUBE_CAMERA=http://192.168.10.249:8080/video
if [[ -f "$PROJECT_DIR/camera.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$PROJECT_DIR/camera.env"
  set +a
fi

export PYTHONPATH="$PROJECT_DIR/.pylibs${PYTHONPATH:+:$PYTHONPATH}"

CAMERA_ARGS=()
if [[ -n "${GESTURECUBE_CAMERA:-}" ]]; then
  CAMERA_ARGS=(--camera "$GESTURECUBE_CAMERA")
fi

exec /usr/bin/python3 "$PROJECT_DIR/app.py" \
  --host 0.0.0.0 \
  --port "${GESTURECUBE_PORT:-8091}" \
  ${CAMERA_ARGS[@]+"${CAMERA_ARGS[@]}"}
