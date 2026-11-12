#!/usr/bin/env bash
set -euo pipefail

echo "== Servicio =="
systemctl is-enabled gesturecube.service 2>/dev/null || true
systemctl is-active gesturecube.service 2>/dev/null || true
echo
systemctl --no-pager --full status gesturecube.service 2>/dev/null | head -20 || true
echo
echo "== Health =="
curl -fsS "http://127.0.0.1:${GESTURECUBE_PORT:-8091}/healthz" || echo "sin respuesta"
echo
