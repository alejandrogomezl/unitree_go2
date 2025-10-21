#!/usr/bin/env bash
set -euo pipefail

### ============================
### Configurables (puedes exportarlos antes de ejecutar)
### ============================
SERVICE_NAME="${SERVICE_NAME:-go2-xbox-control}"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"          # ruta del proyecto (con backend/, frontend/, requirements.txt)
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"     # ruta del venv
PYTHON_BIN="${PYTHON_BIN:-python3}"           # o python3.10, etc.
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"                       # ¡déjalo en 1 para mantener el singleton!

# Usuario que ejecutará el servicio (por defecto, el usuario que lanzó sudo)
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$USER}}"
SERVICE_GROUP="${SERVICE_GROUP:-$SERVICE_USER}"

### ============================
### Paquetes base (Debian/Ubuntu/RPi)
### ============================
echo "[1/5] Instalando paquetes del sistema (python-venv, pip, SDL para pygame)…"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-venv python3-pip \
  libffi-dev build-essential \
  libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 libsdl2-mixer-2.0-0 \
  libjpeg-dev zlib1g-dev

### ============================
### Crear venv + instalar deps
### ============================
echo "[2/5] Creando venv en: $VENV_DIR"
mkdir -p "$VENV_DIR"
$PYTHON_BIN -m venv "$VENV_DIR"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "[3/5] Instalando requirements…"
python -m pip install -U pip wheel setuptools
if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
  pip install -r "$PROJECT_DIR/requirements.txt"
else
  echo "⚠️  No se encontró $PROJECT_DIR/requirements.txt — continúo igualmente."
fi

# (Opcional) instala el driver local si existe
if [[ -d "$PROJECT_DIR/unitree_webrtc_connect" ]]; then
  echo "Se detectó unitree_webrtc_connect local → instalando en editable…"
  pip install -e "$PROJECT_DIR/unitree_webrtc_connect"
fi

deactivate

### ============================
### Servicio systemd
### ============================
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[4/5] Creando servicio systemd: $SERVICE_FILE"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Go2 Xbox Control (FastAPI + Uvicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=${VENV_DIR}/bin/uvicorn backend.server:app --host ${HOST} --port ${PORT} --workers ${WORKERS}
Restart=always
RestartSec=2
# Evita problemas con watchers/websockets
LimitNOFILE=65535

# Logs a journalctl (recomendado). Si prefieres archivos, cambia a append: y crea la ruta.
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

### ============================
### Habilitar + arrancar
### ============================
echo "[5/5] Habilitando y arrancando el servicio…"
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"

echo
echo "✅ Listo."
echo "Servicio:   ${SERVICE_NAME}.service"
echo "Directorio: ${PROJECT_DIR}"
echo "Venv:       ${VENV_DIR}"
echo "Escuchando: http://${HOST}:${PORT}"
echo
echo "Comandos útiles:"
echo "  systemctl status ${SERVICE_NAME}"
echo "  journalctl -u ${SERVICE_NAME} -f"
echo "  systemctl restart ${SERVICE_NAME}"
echo "  systemctl stop ${SERVICE_NAME}"
echo
echo "Para acceder desde otro dispositivo en tu LAN, usa la IP de este equipo y el puerto ${PORT}."
