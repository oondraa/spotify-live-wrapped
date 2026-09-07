#!/usr/bin/env bash
# Instalátor pro Linux server.
# Nastaví virtuální prostředí, .env (API klíče, přihlašovací údaje),
# provede jednorázovou autorizaci vůči Spotify API a volitelně
# nainstaluje systemd služby pro běh na pozadí.
#
# Použití: cd spotify-live-wrapped && bash deploy/install.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
VENV_DIR="$PROJECT_ROOT/.venv"

echo "== Spotify Live Wrapped - instalace =="
echo "Instalační adresář: $PROJECT_ROOT"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 nebyl nalezen. Nainstaluj ho (např. 'sudo apt install python3 python3-venv') a spusť znovu." >&2
    exit 1
fi

# --- 1. Virtuální prostředí a závislosti ---
if [ ! -d "$VENV_DIR" ]; then
    echo "-> Vytvářím virtuální prostředí..."
    python3 -m venv "$VENV_DIR"
fi
echo "-> Instaluji závislosti..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt" --quiet
echo "   Hotovo."
echo

# --- 2. .env konfigurace ---
if [ -f "$ENV_FILE" ]; then
    read -r -p ".env už existuje, přepsat novým nastavením? [y/N]: " overwrite
    overwrite=${overwrite:-N}
else
    overwrite="y"
fi

if [[ "$overwrite" =~ ^[Yy]$ ]]; then
    echo
    echo "-- Spotify API (https://developer.spotify.com/dashboard) --"
    read -r -p "SPOTIFY_CLIENT_ID: " SPOTIFY_CLIENT_ID
    read -r -p "SPOTIFY_CLIENT_SECRET: " SPOTIFY_CLIENT_SECRET
    read -r -p "SPOTIFY_REDIRECT_URI [http://127.0.0.1:8080]: " SPOTIFY_REDIRECT_URI
    SPOTIFY_REDIRECT_URI=${SPOTIFY_REDIRECT_URI:-http://127.0.0.1:8080}
    echo "   (Musí přesně odpovídat Redirect URI nastavené v Spotify Dashboardu.)"

    echo
    echo "-- Přihlášení do webového dashboardu --"
    read -r -p "ADMIN_USERNAME: " ADMIN_USERNAME
    read -r -s -p "ADMIN_PASSWORD (vstup se nezobrazuje): " ADMIN_PASSWORD
    echo
    FLASK_SECRET_KEY="$("$VENV_DIR/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"

    echo
    echo "-- Volitelné nastavení (Enter = výchozí hodnota) --"
    read -r -p "APP_TITLE [Spotify Live Wrapped]: " APP_TITLE
    APP_TITLE=${APP_TITLE:-"Spotify Live Wrapped"}
    read -r -p "WEB_PORT [5000]: " WEB_PORT
    WEB_PORT=${WEB_PORT:-5000}
    read -r -p "COLLECT_INTERVAL_SECONDS [600]: " COLLECT_INTERVAL_SECONDS
    COLLECT_INTERVAL_SECONDS=${COLLECT_INTERVAL_SECONDS:-600}

    cat > "$ENV_FILE" <<EOF
SPOTIFY_CLIENT_ID=$SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET=$SPOTIFY_CLIENT_SECRET
SPOTIFY_REDIRECT_URI=$SPOTIFY_REDIRECT_URI

ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD
FLASK_SECRET_KEY=$FLASK_SECRET_KEY

APP_TITLE=$APP_TITLE
WEB_HOST=0.0.0.0
WEB_PORT=$WEB_PORT
COLLECT_INTERVAL_SECONDS=$COLLECT_INTERVAL_SECONDS
EOF
    chmod 600 "$ENV_FILE"
    echo "-> .env uložen (oprávnění 600)."
else
    echo "-> Ponechávám stávající .env."
fi

mkdir -p "$PROJECT_ROOT/data"
echo

# --- 3. Autorizace vůči Spotify API ---
read -r -p "Provést teď autorizaci Spotify účtu (potřeba jen jednou)? [Y/n]: " do_auth
do_auth=${do_auth:-Y}
AUTH_OK=0
if [[ "$do_auth" =~ ^[Yy]$ ]]; then
    "$VENV_DIR/bin/python" "$PROJECT_ROOT/scripts/authorize.py" && AUTH_OK=1
else
    echo "-> Přeskočeno. Před spuštěním collectoru spusť ručně:"
    echo "   $VENV_DIR/bin/python $PROJECT_ROOT/scripts/authorize.py"
fi
echo

# --- 4. systemd služby (volitelné) ---
read -r -p "Nainstalovat systemd služby pro běh na pozadí (vyžaduje sudo)? [y/N]: " do_systemd
do_systemd=${do_systemd:-N}

if [[ "$do_systemd" =~ ^[Yy]$ ]]; then
    if ! command -v systemctl >/dev/null 2>&1; then
        echo "systemctl nenalezen, přeskočeno." >&2
    else
        read -r -p "Uživatel, pod kterým mají služby běžet [$(whoami)]: " SERVICE_USER
        SERVICE_USER=${SERVICE_USER:-$(whoami)}
        WEB_HOST_VAL="0.0.0.0"
        WEB_PORT_VAL="$(grep -E '^WEB_PORT=' "$ENV_FILE" | cut -d= -f2- || echo 5000)"
        WEB_PORT_VAL=${WEB_PORT_VAL:-5000}

        for name in spotify-collector spotify-web; do
            sed \
                -e "s|__INSTALL_DIR__|$PROJECT_ROOT|g" \
                -e "s|__SERVICE_USER__|$SERVICE_USER|g" \
                -e "s|__WEB_HOST__|$WEB_HOST_VAL|g" \
                -e "s|__WEB_PORT__|$WEB_PORT_VAL|g" \
                "$PROJECT_ROOT/deploy/systemd/${name}.service.template" \
                | sudo tee "/etc/systemd/system/${name}.service" > /dev/null
        done

        sudo systemctl daemon-reload
        sudo systemctl enable spotify-web
        sudo systemctl restart spotify-web
        echo "-> spotify-web nastartován a povolen při bootu."

        if [ "$AUTH_OK" -eq 1 ]; then
            sudo systemctl enable spotify-collector
            sudo systemctl restart spotify-collector
            echo "-> spotify-collector nastartován a povolen při bootu."
        else
            sudo systemctl enable spotify-collector
            echo "-> spotify-collector povolen při bootu, ale NEspuštěn (nejdřív dokonči autorizaci):"
            echo "   $VENV_DIR/bin/python $PROJECT_ROOT/scripts/authorize.py && sudo systemctl start spotify-collector"
        fi
    fi
else
    echo "-> systemd přeskočen. Ruční spuštění:"
    echo "   $VENV_DIR/bin/python $PROJECT_ROOT/app/collector.py   (sběr dat, běží na popředí)"
    echo "   $VENV_DIR/bin/gunicorn --chdir $PROJECT_ROOT/app --bind 0.0.0.0:5000 web:app   (web dashboard)"
fi

echo
echo "== Instalace dokončena =="
