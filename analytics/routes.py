"""
Rutes HTTP de l'analítica.

  - ``POST /api/pulse``: recollida pública i anònima (la crida ``js/main.js``).
  - ``GET /stats/<token>``: tauler privat; només hi accedeix qui té l'enllaç.
  - ``GET /stats/<token>/report``: informe JSON (rang, granularitat, filtres).
  - ``GET /stats/<token>/realtime``: visitants actius ara mateix.
  - ``GET /stats/<token>/export.csv``: exportació de les dades filtrades.
"""

from __future__ import annotations

import csv
import hmac
import io
import json
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import (Blueprint, Response, abort, jsonify, redirect, request,
                   send_from_directory)

from analytics.domain import (DIMENSIONS, EVENT_CONVERSION, EVENT_PAGEVIEW,
                              Event)
from analytics.enrich import (GeoLocation, GeoLocator, anonymous_visitor_id,
                              classify_traffic, is_bot, is_public_ip,
                              local_day, parse_user_agent)
from analytics.report import (apply_filters, build_report, pick_interval,
                              realtime_summary)
from analytics.store import EventStore

logger = logging.getLogger(__name__)

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")
EVENT_ID_RE = re.compile(r"^[a-f0-9]{32}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BODY_BYTES = 4096
MAX_RANGE_DAYS = 800
CACHE_TTL_SECONDS = 60
COLLECT_LIMIT_PER_HOUR = 600
CONVERSION_NAMES = {"contact_submit"}


@dataclass
class AnalyticsConfig:
    """
    Configuració injectada al blueprint.

    Example:
        >>> AnalyticsConfig(dashboard_token="…", salt="…",
        ...                 own_hosts={"juditcamps.com"})
    """

    dashboard_token: str
    salt: str
    own_hosts: set[str] = field(default_factory=set)
    timezone_name: str = "Europe/Madrid"

    @classmethod
    def from_env(cls) -> "AnalyticsConfig":
        token = os.environ.get("STATS_TOKEN", "")
        salt = os.environ.get("ANALYTICS_SALT") or token or secrets.token_hex(32)
        hosts = os.environ.get(
            "ANALYTICS_OWN_HOSTS",
            "juditcamps.com,www.juditcamps.com,localhost,127.0.0.1",
        )
        return cls(
            dashboard_token=token,
            salt=salt,
            own_hosts={host.strip() for host in hosts.split(",") if host.strip()},
        )


class _EventCache:
    """Memòria cau breu de consultes (el tauler fa diverses crides seguides)."""

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._entries: dict[tuple, tuple[float, list[Event]]] = {}
        self._lock = threading.Lock()

    def query(self, start: datetime, end: datetime) -> list[Event]:
        key = (start, end)
        now = time.monotonic()
        with self._lock:
            cached = self._entries.get(key)
            if cached and now - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]
        events = self._store.query(start, end)
        with self._lock:
            if len(self._entries) > 32:
                self._entries.clear()
            self._entries[key] = (now, events)
        return events


class _RateLimiter:
    """Límit d'esdeveniments per IP i hora (per instància)."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > now - 3600]
            allowed = len(hits) < self._limit
            if allowed:
                hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > 10_000:
                self._hits.clear()
            return allowed


def client_ip_from_request() -> str:
    """
    IP real del client darrere de Google Front End + nginx.

    GFE afegeix la IP del client al final de ``X-Forwarded-For`` i nginx hi
    afegeix la del GFE (no pública); per això es pren l'última IP pública i no
    la primera, que el client pot falsejar.
    """
    forwarded = [part.strip() for part in
                 request.headers.get("X-Forwarded-For", "").split(",")
                 if part.strip()]
    for candidate in reversed(forwarded):
        if is_public_ip(candidate):
            return candidate
    return forwarded[0] if forwarded else (request.remote_addr or "")


def normalize_path(raw_url: str) -> str:
    """Normalitza la ruta perquè /privadesa i /privadesa.html comptin igual."""
    path = raw_url.split("?", 1)[0].split("#", 1)[0] or "/"
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r"/{2,}", "/", path)[:200]
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    elif path.endswith(".html"):
        path = path[: -len(".html")]
    return path or "/"


def _parse_day(value: str | None, fallback: date) -> date:
    if value and DATE_RE.match(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback


def _error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": {"message": message, "status": status}}), status


def create_analytics_blueprint(store: EventStore | None, geolocator: GeoLocator,
                               config: AnalyticsConfig) -> Blueprint:
    """
    Crea el blueprint d'analítica amb les dependències injectades.

    Args:
        store: persistència d'esdeveniments (``None`` desactiva l'analítica).
        geolocator: servei de geolocalització d'IP.
        config: token del tauler, sal del hash i dominis propis.

    Returns:
        Blueprint de Flask a registrar a l'aplicació.

    Example:
        >>> app.register_blueprint(create_analytics_blueprint(
        ...     build_store_from_env(), build_geolocator_from_env(),
        ...     AnalyticsConfig.from_env()))
    """
    blueprint = Blueprint("analytics", __name__)
    tz = ZoneInfo(config.timezone_name)
    cache = _EventCache(store) if store else None
    rate_limiter = _RateLimiter(COLLECT_LIMIT_PER_HOUR)

    # ------------------------------------------------------------------
    # Recollida pública
    # ------------------------------------------------------------------
    @blueprint.post("/api/pulse")
    def collect() -> tuple:
        """Rep una visita, un temps d'interacció o una conversió."""
        no_content = ("", 204)
        if store is None or (request.content_length or 0) > MAX_BODY_BYTES:
            return no_content

        own_hosts = config.own_hosts | {request.host.split(":")[0]}
        origin_host = urlsplit(request.headers.get("Origin", "")).hostname
        if origin_host and origin_host not in own_hosts:
            return _error("Origen no permès.", 403)

        if request.headers.get("Sec-GPC") == "1":
            return no_content
        user_agent = request.headers.get("User-Agent", "")[:400]
        if is_bot(user_agent):
            return no_content

        try:
            payload = json.loads(request.get_data(as_text=True) or "{}")
        except json.JSONDecodeError:
            return _error("JSON no vàlid.", 400)
        if not isinstance(payload, dict):
            return _error("JSON no vàlid.", 400)

        event_id = str(payload.get("id", ""))
        if not EVENT_ID_RE.match(event_id):
            return _error("Identificador no vàlid.", 400)

        ip_address = client_ip_from_request()
        if not rate_limiter.allow(ip_address):
            return _error("Massa peticions.", 429)

        try:
            kind = payload.get("t")
            if kind == "engagement":
                engaged_ms = max(0, min(int(payload.get("e") or 0), 3_600_000))
                scroll_pct = max(0, min(int(payload.get("s") or 0), 100))
                store.update_engagement(event_id, engaged_ms, scroll_pct)
                return no_content
            if kind not in (EVENT_PAGEVIEW, EVENT_CONVERSION):
                return _error("Tipus d'esdeveniment no vàlid.", 400)

            name = str(payload.get("n") or "")[:40]
            if kind == EVENT_CONVERSION and name not in CONVERSION_NAMES:
                return _error("Conversió desconeguda.", 400)

            now = datetime.now(timezone.utc)
            page_url = str(payload.get("u") or "/")[:600]
            traffic = classify_traffic(
                page_url, str(payload.get("r") or "")[:600], own_hosts)
            location = (geolocator.locate(ip_address) if is_public_ip(ip_address)
                        else GeoLocation())
            browser, operating_system, device = parse_user_agent(
                user_agent, int(payload.get("sw") or 0),
                int(payload.get("tp") or 0))

            store.add(Event(
                event_id=event_id,
                ts=now,
                type=kind,
                name=name,
                visitor=anonymous_visitor_id(config.salt, local_day(now),
                                             ip_address, user_agent),
                path=normalize_path(page_url),
                lang=str(payload.get("l") or "")[:8].lower(),
                channel=traffic.channel,
                source=traffic.source,
                referrer_host=traffic.referrer_host,
                utm_source=traffic.utm_source,
                utm_medium=traffic.utm_medium,
                utm_campaign=traffic.utm_campaign,
                country=location.country,
                region=location.region,
                city=location.city,
                device=device,
                browser=browser,
                os=operating_system,
            ))
        except (TypeError, ValueError):
            return _error("Dades no vàlides.", 400)
        except Exception as error:  # noqa: BLE001 - l'analítica mai no falla en sec
            logger.warning("No s'ha pogut desar l'esdeveniment: %s", error)
        return no_content

    # ------------------------------------------------------------------
    # Tauler privat
    # ------------------------------------------------------------------
    def require_token(token: str) -> None:
        """Sense token configurat o amb token incorrecte: 404 (no revela res)."""
        expected = config.dashboard_token
        if not expected or not hmac.compare_digest(token.encode(),
                                                   expected.encode()):
            abort(404)

    def private(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        # L'enllaç conté el token: que no surti mai com a referent.
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def requested_range() -> tuple[datetime, datetime, date, date]:
        today = datetime.now(tz).date()
        end_day = _parse_day(request.args.get("to"), today)
        start_day = _parse_day(request.args.get("from"),
                               end_day - timedelta(days=29))
        if start_day > end_day:
            start_day, end_day = end_day, start_day
        if (end_day - start_day).days > MAX_RANGE_DAYS:
            start_day = end_day - timedelta(days=MAX_RANGE_DAYS)
        start = datetime.combine(start_day, datetime.min.time(), tz)
        end = datetime.combine(end_day + timedelta(days=1),
                               datetime.min.time(), tz)
        return start, end, start_day, end_day

    def requested_filters() -> dict[str, str]:
        return {dimension: request.args[f"f_{dimension}"][:200]
                for dimension in DIMENSIONS
                if f"f_{dimension}" in request.args}

    @blueprint.get("/stats/<token>")
    def dashboard_redirect(token: str) -> Response:
        """Amb barra final, les rutes relatives del tauler resolen bé."""
        require_token(token)
        return private(redirect(f"/stats/{token}/", code=308))

    @blueprint.get("/stats/<token>/")
    def dashboard(token: str) -> Response:
        """Pàgina del tauler (HTML estàtic; les dades arriben per JSON)."""
        require_token(token)
        return private(send_from_directory(DASHBOARD_DIR, "index.html"))

    @blueprint.get("/stats/<token>/assets/<path:filename>")
    def dashboard_asset(token: str, filename: str) -> Response:
        require_token(token)
        if filename not in {"dashboard.js", "dashboard.css"}:
            abort(404)
        return private(send_from_directory(DASHBOARD_DIR, filename))

    @blueprint.get("/stats/<token>/report")
    def report(token: str) -> tuple:
        """Informe complet: KPI, evolució, desglossaments i mapa de calor."""
        require_token(token)
        if cache is None:
            return _error("L'analítica no està configurada.", 503)
        start, end, start_day, end_day = requested_range()
        previous_start = start - (end - start)
        try:
            current_events = cache.query(start, end)
            previous_events = cache.query(previous_start, start)
        except Exception as error:  # noqa: BLE001
            logger.error("Error consultant l'analítica: %s", error)
            return _error("No s'han pogut llegir les dades.", 502)

        interval = pick_interval(start_day, end_day + timedelta(days=1),
                                 request.args.get("interval", "auto"))
        filters = requested_filters()
        body = build_report(current_events, previous_events, start, end,
                            interval, filters, tz)
        body["range"] = {
            "from": start_day.isoformat(),
            "to": end_day.isoformat(),
            "previous_from": previous_start.date().isoformat(),
            "previous_to": (start - timedelta(days=1)).date().isoformat(),
            "interval": interval,
            "timezone": config.timezone_name,
        }
        body["filters"] = filters
        return private(jsonify(body)), 200

    @blueprint.get("/stats/<token>/realtime")
    def realtime(token: str) -> tuple:
        require_token(token)
        if store is None:
            return _error("L'analítica no està configurada.", 503)
        now = datetime.now(timezone.utc)
        try:
            events = store.query(now - timedelta(minutes=5), now)
        except Exception as error:  # noqa: BLE001
            logger.error("Error consultant temps real: %s", error)
            return _error("No s'han pogut llegir les dades.", 502)
        return private(jsonify(realtime_summary(events, now))), 200

    @blueprint.get("/stats/<token>/export.csv")
    def export_csv(token: str) -> Response:
        """Exporta els esdeveniments filtrats per analitzar-los en un full."""
        require_token(token)
        if cache is None:
            abort(503)
        start, end, start_day, end_day = requested_range()
        try:
            events = apply_filters(cache.query(start, end), requested_filters())
        except Exception as error:  # noqa: BLE001
            logger.error("Error exportant l'analítica: %s", error)
            abort(502)

        buffer = io.StringIO()
        columns = ["ts_local", "type", "name", "visitor", *DIMENSIONS,
                   "engaged_s", "scroll_pct"]
        writer = csv.writer(buffer)
        writer.writerow(columns)
        for event in events:
            writer.writerow([
                event.ts.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
                event.type, event.name, event.visitor,
                *[getattr(event, dimension) for dimension in DIMENSIONS],
                round(event.engaged_ms / 1000, 1), event.scroll_pct,
            ])
        response = Response(buffer.getvalue(), mimetype="text/csv")
        filename = f"juditcamps-audiencia-{start_day}-{end_day}.csv"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{filename}"')
        return private(response)

    return blueprint
