#!/usr/bin/env bash
# Linux server installer.
# Sets up a virtual environment, writes .env (API keys, login
# credentials), runs the one-time Spotify API authorization, and
# optionally installs systemd services for running in the background.
#
# Usage: cd spotify-live-wrapped && bash deploy/install.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
VENV_DIR="$PROJECT_ROOT/.venv"

echo "== Spotify Live Wrapped - installer =="
echo "Install directory: $PROJECT_ROOT"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 was not found. Install it (e.g. 'sudo apt install python3 python3-venv') and run again." >&2
    exit 1
fi

# --- 1. Virtual environment and dependencies ---
if [ ! -d "$VENV_DIR" ]; then
    echo "-> Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
echo "-> Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt" --quiet
echo "   Done."
echo

# --- 2. .env configuration ---
if [ -f "$ENV_FILE" ]; then
    read -r -p ".env already exists, overwrite with new settings? [y/N]: " overwrite
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
    echo "   (Must exactly match the Redirect URI configured in the Spotify Dashboard.)"

    echo
    echo "-- Web dashboard login --"
    read -r -p "ADMIN_USERNAME: " ADMIN_USERNAME
    read -r -s -p "ADMIN_PASSWORD (input hidden): " ADMIN_PASSWORD
    echo
    FLASK_SECRET_KEY="$("$VENV_DIR/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"

    echo
    echo "-- Optional settings (press Enter for default) --"
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
    echo "-> .env saved (permissions 600)."
else
    echo "-> Keeping existing .env."
fi

mkdir -p "$PROJECT_ROOT/data"
echo

# --- 3. Spotify API authorization ---
read -r -p "Authorize the Spotify account now (only needed once)? [Y/n]: " do_auth
do_auth=${do_auth:-Y}
AUTH_OK=0
if [[ "$do_auth" =~ ^[Yy]$ ]]; then
    "$VENV_DIR/bin/python" "$PROJECT_ROOT/scripts/authorize.py" && AUTH_OK=1
else
    echo "-> Skipped. Before starting the collector, run manually:"
    echo "   $VENV_DIR/bin/python $PROJECT_ROOT/scripts/authorize.py"
fi
echo

# --- 4. systemd services (optional) ---
read -r -p "Install systemd services to run in the background (requires sudo)? [y/N]: " do_systemd
do_systemd=${do_systemd:-N}

if [[ "$do_systemd" =~ ^[Yy]$ ]]; then
    if ! command -v systemctl >/dev/null 2>&1; then
        echo "systemctl not found, skipping." >&2
    else
        read -r -p "User the services should run as [$(whoami)]: " SERVICE_USER
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
        echo "-> spotify-web started and enabled at boot."

        if [ "$AUTH_OK" -eq 1 ]; then
            sudo systemctl enable spotify-collector
            sudo systemctl restart spotify-collector
            echo "-> spotify-collector started and enabled at boot."
        else
            sudo systemctl enable spotify-collector
            echo "-> spotify-collector enabled at boot, but NOT started (finish authorization first):"
            echo "   $VENV_DIR/bin/python $PROJECT_ROOT/scripts/authorize.py && sudo systemctl start spotify-collector"
        fi
    fi
else
    echo "-> systemd skipped. Manual start:"
    echo "   $VENV_DIR/bin/python $PROJECT_ROOT/app/collector.py   (data collection, runs in foreground)"
    echo "   $VENV_DIR/bin/gunicorn --chdir $PROJECT_ROOT/app --bind 0.0.0.0:5000 web:app   (web dashboard)"
fi

echo
echo "== Installation complete =="
