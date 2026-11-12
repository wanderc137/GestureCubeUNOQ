#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Este script debe ejecutarse como root (sudo)." >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="$PROJECT_DIR/systemd/gesturecube.service"
UNIT_DST="/etc/systemd/system/gesturecube.service"

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "No se encontró $UNIT_SRC" >&2
  exit 1
fi

sed "s|/home/arduino/GestureCubeUNOQ|$PROJECT_DIR|g" "$UNIT_SRC" > "$UNIT_DST"
chmod 644 "$UNIT_DST"

systemctl daemon-reload
systemctl enable --now gesturecube.service
systemctl --no-pager --full status gesturecube.service || true

echo
echo "GestureCube instalado como servicio."
echo "Panel: http://$(hostname -I | awk '{print $1}'):8091/"
