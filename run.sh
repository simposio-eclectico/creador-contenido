#!/usr/bin/env bash
# run.sh - Instala dependencias (si hace falta) e inicia el servidor web.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creando entorno virtual en $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Instalando/actualizando dependencias..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "Iniciando servidor..."
exec python3 server.py
