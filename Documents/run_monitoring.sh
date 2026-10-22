#!/usr/bin/env bash
#
# run_monitoring.sh — Ejecuta el escaneo de clones y, al terminar, genera el
# certificado de vigilancia a partir de ese mismo resultado.
#
#   ./run_monitoring.sh                 (pide el dominio de forma interactiva)
#   ./run_monitoring.sh tusitio.com     (pasa el dominio al escáner)
#
set -euo pipefail

# Directorio del script (para encontrar los .py aunque lo llames desde otro lado).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Usa el intérprete del venv si existe; si no, python3 del sistema.
if [ -x "$DIR/venv/bin/python" ]; then
    PY="$DIR/venv/bin/python"
else
    PY="python3"
fi

echo "==> [1/2] Escaneo de clones"
"$PY" "$DIR/clone_scan.py" "$@"

# Solo genera el certificado si el escaneo dejó un reporte.
if [ -f "$DIR/ultimo_reporte.txt" ]; then
    echo
    echo "==> [2/2] Generando certificado de vigilancia"
    "$PY" "$DIR/build_certificate.py"
else
    echo
    echo "[!] El escaneo no dejó reporte; no se genera certificado." >&2
    exit 1
fi
