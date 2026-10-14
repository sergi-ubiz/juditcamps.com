"""
Backend propi del formulari de contacte de juditcamps.com.

Exposa un únic endpoint POST /api/contact que:
  1. Valida els camps del formulari.
  2. Verifica el token de Cloudflare Turnstile contra el servidor (anti-spam).
  3. Envia el missatge per correu a l'adreça de destí mitjançant el SMTP
     de Google Workspace de la Judit (sense serveis de formularis externs).

Tota la configuració sensible s'injecta per variables d'entorn (Cloud Run /
Secret Manager); res no queda escrit al codi.
"""

import os
import re
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import requests
from flask import Flask, abort, jsonify, request, send_from_directory

from analytics import create_analytics_blueprint
from analytics.enrich import build_geolocator_from_env
from analytics.routes import AnalyticsConfig
from analytics.store import build_store_from_env

app = Flask(__name__)

# Analítica d'audiències pròpia (sense cookies): recollida a /api/pulse i
# tauler privat a /stats/<STATS_TOKEN>.
app.register_blueprint(create_analytics_blueprint(
    build_store_from_env(), build_geolocator_from_env(),
    AnalyticsConfig.from_env()))

# ---------------------------------------------------------------------------
# Configuració (variables d'entorn)
# ---------------------------------------------------------------------------
TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
CONTACT_TO = os.environ.get("CONTACT_TO", "info@juditcamps.com")
CONTACT_FROM = os.environ.get("CONTACT_FROM", SMTP_USER or CONTACT_TO)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# Secret de prova oficial de Cloudflare (sempre valida); només per a ús local.
TURNSTILE_TEST_SECRET = "1x0000000000000000000000000000000AA"

# En local sense SMTP, el correu es mostra per consola en lloc d'enviar-se.
LOCAL_DRY_RUN = False

# Data de la versió de privadesa.html acceptada; actualitzar-la si canvia el text.
PRIVACY_POLICY_VERSION = "2026-10-13"

# Límits de longitud (coherents amb els atributs maxlength del formulari)
MAX_LENGTHS = {
    "nom": 100,
    "email": 150,
    "telefon": 15,
    "missatge": 2000,
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+ ]{9,15}$")

# Rate-limiting bàsic en memòria (per instància): IP -> [timestamps]
_RATE_BUCKET: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW_SECONDS = 3600
RATE_LIMIT_MAX_REQUESTS = 5


def _client_ip() -> str:
    """Retorna la IP del client tenint en compte el proxy de Cloud Run/nginx."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # El primer valor és la IP original del client.
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_limited(ip_address: str) -> bool:
    """Comprova i actualitza el límit d'enviaments per IP."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = [t for t in _RATE_BUCKET.get(ip_address, []) if t > window_start]
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        _RATE_BUCKET[ip_address] = timestamps
        return True
    timestamps.append(now)
    _RATE_BUCKET[ip_address] = timestamps
    return False


def _verify_turnstile(token: str, ip_address: str) -> bool:
    """Verifica el token de Turnstile contra el servidor de Cloudflare."""
    if not TURNSTILE_SECRET:
        # Sense secret configurat no podem garantir anti-spam: rebutgem.
        return False
    try:
        response = requests.post(
            TURNSTILE_VERIFY_URL,
            data={
                "secret": TURNSTILE_SECRET,
                "response": token,
                "remoteip": ip_address,
            },
            timeout=10,
        )
        response.raise_for_status()
        return bool(response.json().get("success"))
    except requests.RequestException:
        return False


def _build_message(data: dict) -> EmailMessage:
    """Construeix el correu electrònic a partir de les dades validades."""
    submitter_name = data["nom"]
    submitter_email = data["email"]
    consent_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    message = EmailMessage()
    message["Subject"] = f"Nova sol·licitud de cita — {submitter_name}"
    message["From"] = formataddr(("Web Judit Camps", CONTACT_FROM))
    message["To"] = CONTACT_TO
    # Permet respondre directament a la persona que ha escrit.
    message["Reply-To"] = formataddr((submitter_name, submitter_email))

    body = (
        "Nou missatge des del formulari de juditcamps.com\n"
        "------------------------------------------------\n\n"
        f"Nom i cognoms: {submitter_name}\n"
        f"Correu: {submitter_email}\n"
        f"Telèfon: {data['telefon']}\n"
        f"Idioma del formulari: {data['idioma']}\n\n"
        "Comentari:\n"
        f"{data['missatge']}\n\n"
        "------------------------------------------------\n"
        f"Consentiment RGPD (art. 6.1.a i 9.2.a) acceptat el {consent_timestamp}, "
        f"política de privadesa versió {PRIVACY_POLICY_VERSION}.\n"
        "Conservació: suprimir aquest correu als 12 mesos de l'última "
        "comunicació si no s'inicia relació professional.\n"
    )
    message.set_content(body)
    return message


def _send_email(message: EmailMessage) -> None:
    """Envia el correu via SMTP amb STARTTLS (Google Workspace)."""
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)


@app.get("/api/health")
def health() -> tuple:
    """Comprovació de salut i de configuració (sense exposar secrets)."""
    return (
        jsonify(
            {
                "status": "ok",
                "turnstile_configured": bool(TURNSTILE_SECRET),
                "smtp_configured": bool(SMTP_USER and SMTP_PASSWORD),
            }
        ),
        200,
    )


@app.post("/api/contact")
def contact() -> tuple:
    """Rep, valida i envia el formulari de contacte."""
    # Si el backend no està configurat, avisem amb un error clar.
    if not (SMTP_USER and SMTP_PASSWORD) and not LOCAL_DRY_RUN:
        return (
            jsonify(
                {
                    "error": {
                        "message": "El servei de correu encara no està configurat.",
                        "status": 503,
                    }
                }
            ),
            503,
        )

    ip_address = _client_ip()
    if _rate_limited(ip_address):
        return (
            jsonify(
                {
                    "error": {
                        "message": "Has enviat massa sol·licituds. Prova-ho més tard.",
                        "status": 429,
                    }
                }
            ),
            429,
        )

    # El formulari s'envia com a multipart/form-data (FormData).
    form = request.form

    # Honeypot: si el camp ocult està ple, és un bot. Responem 200 silenciós.
    if form.get("_gotcha"):
        return jsonify({"ok": True}), 200

    # Verificació del captcha Turnstile al servidor.
    token = form.get("cf-turnstile-response", "")
    if not _verify_turnstile(token, ip_address):
        return (
            jsonify(
                {
                    "error": {
                        "message": "La verificació de seguretat ha fallat.",
                        "status": 400,
                    }
                }
            ),
            400,
        )

    # Recollida i validació dels camps.
    data = {
        "nom": (form.get("nom") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "telefon": (form.get("telefon") or "").strip(),
        "missatge": (form.get("missatge") or "").strip(),
        "idioma": "castellà" if form.get("idioma") == "es" else "català",
    }

    errors = []
    for field, max_length in MAX_LENGTHS.items():
        if not data[field]:
            errors.append(f"El camp «{field}» és obligatori.")
        elif len(data[field]) > max_length:
            errors.append(f"El camp «{field}» és massa llarg.")

    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors.append("El correu electrònic no és vàlid.")
    if data["telefon"] and not PHONE_RE.match(data["telefon"]):
        errors.append("El telèfon no és vàlid.")
    if not form.get("consentiment"):
        errors.append("Cal acceptar la política de privadesa.")

    # Comprovació extra del remitent per evitar capçaleres mal formades.
    if data["email"] and not parseaddr(data["email"])[1]:
        errors.append("El correu electrònic no és vàlid.")

    if errors:
        return (
            jsonify({"error": {"message": " ".join(errors), "status": 400}}),
            400,
        )

    # Construcció i enviament del correu.
    try:
        message = _build_message(data)
        if LOCAL_DRY_RUN:
            print(message, flush=True)
        else:
            _send_email(message)
    except (smtplib.SMTPException, OSError):
        return (
            jsonify(
                {
                    "error": {
                        "message": "No s'ha pogut enviar el missatge. Torna-ho a provar.",
                        "status": 502,
                    }
                }
            ),
            502,
        )

    return jsonify({"ok": True}), 200


def _serve_local_static(path: str = ""):
    """Serveix l'estàtic en local imitant nginx (index i URLs sense extensió)."""
    root = os.path.dirname(os.path.abspath(__file__))
    hidden_dirs = {"credentials", "assets-src", ".git", "analytics", "geo"}
    if path.split("/")[0] in hidden_dirs or path.endswith(".sqlite3"):
        abort(404)
    candidates = [path, f"{path}.html", os.path.join(path, "index.html")]
    for candidate in candidates:
        full_path = os.path.join(root, candidate)
        if candidate and os.path.isfile(full_path):
            return send_from_directory(root, candidate)
    return send_from_directory(root, "index.html")


if __name__ == "__main__":
    # Execució local (en producció s'usa gunicorn darrere d'nginx): serveix també
    # la web, usa el secret de prova de Turnstile i, sense SMTP, no envia correus.
    TURNSTILE_SECRET = TURNSTILE_SECRET or TURNSTILE_TEST_SECRET
    LOCAL_DRY_RUN = not (SMTP_USER and SMTP_PASSWORD)
    app.add_url_rule("/", "local_index", _serve_local_static)
    app.add_url_rule("/<path:path>", "local_static", _serve_local_static)
    local_port = int(os.environ.get("PORT", "8080"))
    print(f"Web local a http://127.0.0.1:{local_port}/", flush=True)
    app.run(host="127.0.0.1", port=local_port, debug=False)
