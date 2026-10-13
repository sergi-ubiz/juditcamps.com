#!/bin/sh
# Arrenca el backend (gunicorn) i el servidor web (nginx) dins el contenidor.
set -e

HTML_DIR="/usr/share/nginx/html"

# Injecta la clau pública de Turnstile a l'HTML si està configurada.
# (La sitekey és pública; el secret viu només al backend.)
if [ -n "$TURNSTILE_SITE_KEY" ]; then
    sed -i "s|TURNSTILE_SITE_KEY|$TURNSTILE_SITE_KEY|g" "$HTML_DIR/index.html" "$HTML_DIR/es/index.html"
fi

# Backend Flask via gunicorn, escoltant en local; nginx hi fa de proxy.
gunicorn --bind 127.0.0.1:8000 --workers 2 --threads 4 --timeout 30 app:app &

# Espera que gunicorn accepti connexions abans d'obrir nginx (port 8080).
# Així Cloud Run no enruta trànsit fins que el backend està llest i evitem
# els 502 de la cursa d'arrencada en fred.
python -c "
import socket, time, sys
for _ in range(60):
    try:
        socket.create_connection(('127.0.0.1', 8000), 1).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.5)
sys.exit(1)
" || echo 'AVÍS: el backend no respon; nginx servirà només l estàtic.'

# nginx en primer pla (procés principal del contenidor).
exec nginx -g 'daemon off;'
