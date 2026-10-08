#!/bin/bash

cd "$(dirname "$0")"

echo "===================================================================="
echo " DESCARGADOR DE AUDIO - YOUTUBE / SOUNDCLOUD / BANDCAMP / RAVEYARD"
echo "===================================================================="
echo " Uso permitido: musica propia, libre, Creative Commons o con permiso."
echo "===================================================================="
echo ""

# ============================================================
# 1) VERIFICAR PYTHON
# ============================================================

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] No se encontró Python 3."

    if command -v apt &> /dev/null; then
        echo "Instalando Python con apt..."
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv
    elif command -v dnf &> /dev/null; then
        echo "Instalando Python con dnf..."
        sudo dnf install -y python3 python3-pip python3-venv
    elif command -v pacman &> /dev/null; then
        echo "Instalando Python con pacman..."
        sudo pacman -Sy --noconfirm python python-pip
    else
        echo "No pude detectar tu gestor de paquetes."
        echo "Instala manualmente: python3, pip y venv."
        exit 1
    fi
fi

# ============================================================
# 2) VERIFICAR VERSIÓN PYTHON
# ============================================================

python3 - <<EOF
import sys
exit(0 if sys.version_info >= (3, 10) else 1)
EOF

if [ $? -ne 0 ]; then
    echo "[ERROR] Necesitas Python 3.10 o superior."
    exit 1
fi

# ============================================================
# 3) VERIFICAR VENV
# ============================================================

if ! python3 -m venv --help &> /dev/null; then
    echo "[AVISO] No se encontró python3-venv."

    if command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y python3-venv
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3-venv
    else
        echo "Instala manualmente el módulo venv de Python."
        exit 1
    fi
fi

# ============================================================
# 4) CREAR ENTORNO VIRTUAL
# ============================================================

if [ ! -f ".venv/bin/python" ]; then
    echo ""
    echo "Creando entorno virtual de Python..."
    python3 -m venv .venv
fi

VENV_PY=".venv/bin/python"

# ============================================================
# 5) INSTALAR / ACTUALIZAR DEPENDENCIAS
# ============================================================

echo ""
echo "Actualizando pip..."
"$VENV_PY" -m pip install --upgrade pip

echo ""
echo "Instalando / actualizando yt-dlp y soporte SOCKS..."
"$VENV_PY" -m pip install --upgrade "yt-dlp[default]" PySocks

# ============================================================
# 6) VERIFICAR FFMPEG
# ============================================================

if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo "[AVISO] No se encontró FFmpeg."
    echo "FFmpeg es necesario para convertir audio a MP3, WAV, FLAC o M4A."

    if command -v apt &> /dev/null; then
        echo "Instalando FFmpeg con apt..."
        sudo apt update
        sudo apt install -y ffmpeg
    elif command -v dnf &> /dev/null; then
        echo "Instalando FFmpeg con dnf..."
        sudo dnf install -y ffmpeg
    elif command -v pacman &> /dev/null; then
        echo "Instalando FFmpeg con pacman..."
        sudo pacman -Sy --noconfirm ffmpeg
    else
        echo "No pude detectar tu gestor de paquetes."
        echo "Instala FFmpeg manualmente."
        exit 1
    fi
fi

# ============================================================
# 7) OPCIONAL: MODO TOR PARA ESTA EJECUCION
# ============================================================

USAR_TOR="${DESCARGADOR_USAR_TOR:-}"

if [ -z "$USAR_TOR" ]; then
    echo ""
    read -r -p "Quieres enrutar las peticiones HTTP/HTTPS por Tor en esta ejecucion? [s/N]: " RESPUESTA_TOR

    case "$RESPUESTA_TOR" in
        s|S|si|SI|Si|y|Y|yes|YES|Yes)
            USAR_TOR="1"
            ;;
        *)
            USAR_TOR="0"
            ;;
    esac
fi

case "$USAR_TOR" in
    1|true|TRUE|s|S|si|SI|Si|y|Y|yes|YES|Yes)
        export DESCARGADOR_USAR_TOR="1"
        export DESCARGADOR_TOR_PROXY="${DESCARGADOR_TOR_PROXY:-socks5h://127.0.0.1:9050}"

        if ! command -v tor &> /dev/null; then
            echo ""
            echo "[AVISO] Tor no esta instalado."

            if command -v apt &> /dev/null; then
                echo "Instalando Tor con apt..."
                sudo apt update
                sudo apt install -y tor
            else
                echo "Instala Tor manualmente y vuelve a ejecutar este archivo."
                exit 1
            fi
        fi

        if command -v systemctl &> /dev/null; then
            if ! systemctl is-active --quiet tor; then
                echo ""
                echo "Iniciando servicio Tor..."
                sudo systemctl enable tor
                sudo systemctl start tor
            fi
        fi

        "$VENV_PY" - <<'EOF'
import socket
import sys

try:
    with socket.create_connection(("127.0.0.1", 9050), timeout=5):
        pass
except OSError as error:
    print(f"[ERROR] No pude conectar al proxy SOCKS de Tor en 127.0.0.1:9050: {error}")
    sys.exit(1)
EOF

        if [ $? -ne 0 ]; then
            echo "Revisa con: systemctl status tor"
            exit 1
        fi

        echo ""
        echo "Modo Tor activado usando: $DESCARGADOR_TOR_PROXY"
        ;;
    *)
        unset DESCARGADOR_USAR_TOR
        ;;
esac

# ============================================================
# 8) EJECUTAR DESCARGADOR
# ============================================================

echo ""
echo "Abriendo descargador..."
echo ""

"$VENV_PY" descargar.py

echo ""
read -p "Presiona ENTER para salir..."
