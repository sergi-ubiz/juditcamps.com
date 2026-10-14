"""
Enriquiment d'una visita a partir de la petició HTTP.

Tot es calcula al servidor i en local: la IP es geolocalitza amb una base de
dades offline (DB-IP Lite) i es descarta immediatament; mai no s'envia a
tercers ni es desa.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geolocalització
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GeoLocation:
    """País (ISO 3166-1 alfa-2), regió i ciutat aproximats d'una IP."""

    country: str = ""
    region: str = ""
    city: str = ""


class GeoLocator(Protocol):
    """Contracte per a qualsevol proveïdor de geolocalització."""

    def locate(self, ip_address: str) -> GeoLocation:
        """Retorna la ubicació aproximada de la IP (o buida si no se sap)."""
        ...


class NullGeoLocator:
    """Geolocalitzador buit (sense base de dades disponible)."""

    def locate(self, ip_address: str) -> GeoLocation:
        return GeoLocation()


class MmdbGeoLocator:
    """
    Geolocalitzador sobre un fitxer MaxMind DB (p. ex. dbip-city-lite.mmdb).

    Example:
        >>> MmdbGeoLocator("/app/geo/dbip-city-lite.mmdb").locate("8.8.8.8")
        GeoLocation(country='US', region='California', city='Mountain View')
    """

    def __init__(self, database_path: str) -> None:
        import maxminddb  # Import tardà: opcional en local.

        self._reader = maxminddb.open_database(database_path)

    def locate(self, ip_address: str) -> GeoLocation:
        try:
            record = self._reader.get(ip_address) or {}
        except (ValueError, TypeError):
            return GeoLocation()
        subdivisions = record.get("subdivisions") or [{}]
        return GeoLocation(
            country=(record.get("country") or {}).get("iso_code", ""),
            region=_localized_name(subdivisions[0]),
            city=_localized_name(record.get("city") or {}),
        )


# DB-IP Lite només porta noms en anglès; les regions d'Espanya, en català.
REGION_NAMES_CA = {
    "Catalonia": "Catalunya",
    "Valencia": "País Valencià",
    "Valencian Community": "País Valencià",
    "Balearic Islands": "Illes Balears",
    "Aragon": "Aragó",
    "Andalusia": "Andalusia",
    "Madrid": "Comunitat de Madrid",
    "Basque Country": "País Basc",
    "Navarre": "Navarra",
    "Castille and León": "Castella i Lleó",
    "Castille-La Mancha": "Castella - la Manxa",
    "Canary Islands": "Illes Canàries",
    "Galicia": "Galícia",
    "Asturias": "Astúries",
    "Murcia": "Múrcia",
    "Cantabria": "Cantàbria",
    "Extremadura": "Extremadura",
    "La Rioja": "La Rioja",
}


def _localized_name(entity: dict) -> str:
    """Nom en castellà si existeix, si no en anglès (traduït si és una regió)."""
    names = entity.get("names") or {}
    name = names.get("es") or names.get("en") or ""
    return REGION_NAMES_CA.get(name, name)


def build_geolocator_from_env() -> GeoLocator:
    """Crea el geolocalitzador segons ``GEOIP_DB_PATH`` (o un de buit)."""
    default_path = os.path.join(os.path.dirname(__file__), "..", "geo",
                                "dbip-city-lite.mmdb")
    database_path = os.environ.get("GEOIP_DB_PATH", default_path)
    if not os.path.isfile(database_path):
        logger.warning("Base de dades GeoIP no trobada a %s", database_path)
        return NullGeoLocator()
    try:
        return MmdbGeoLocator(database_path)
    except (ImportError, OSError, ValueError) as error:
        logger.warning("No s'ha pogut obrir la base GeoIP: %s", error)
        return NullGeoLocator()


def is_public_ip(ip_address: str) -> bool:
    """Indica si la IP és pública (les privades no es poden geolocalitzar)."""
    try:
        return ipaddress.ip_address(ip_address).is_global
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Identificador anònim de visitant
# ---------------------------------------------------------------------------
def anonymous_visitor_id(secret: str, day: str, ip_address: str,
                         user_agent: str) -> str:
    """
    Hash diari i no reversible del visitant (model de Plausible/Fathom).

    Canvia cada dia, de manera que no permet seguir ningú entre dies ni
    reconstruir la IP. Amb el mateix ``secret`` és estable entre instàncies.
    """
    message = f"{day}|{ip_address}|{user_agent}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Navegador, sistema operatiu i dispositiu
# ---------------------------------------------------------------------------
BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|scrap|headless|lighthouse|pagespeed|preview|"
    r"monitor|uptime|python|curl|wget|httpclient|okhttp|java/|go-http|axios|"
    r"phantom|selenium|puppeteer|playwright|facebookexternalhit|embedly|"
    r"whatsapp|telegrambot|discord|skypeuripreview",
    re.IGNORECASE,
)

BROWSER_RULES = (
    ("Edge", re.compile(r"Edg(e|A|iOS)?/")),
    ("Opera", re.compile(r"OPR/|Opera")),
    ("Samsung Internet", re.compile(r"SamsungBrowser/")),
    ("Firefox", re.compile(r"Firefox/|FxiOS/")),
    ("Chrome", re.compile(r"Chrome/|CriOS/")),
    ("Safari", re.compile(r"Safari/")),
)

OS_RULES = (
    ("iOS", re.compile(r"iPhone|iPod")),
    ("iPadOS", re.compile(r"iPad")),
    ("Android", re.compile(r"Android")),
    ("Windows", re.compile(r"Windows")),
    ("ChromeOS", re.compile(r"CrOS")),
    ("macOS", re.compile(r"Macintosh|Mac OS X")),
    ("Linux", re.compile(r"Linux")),
)


def is_bot(user_agent: str) -> bool:
    """Detecta robots, eines automàtiques i previsualitzadors d'enllaços."""
    return not user_agent or bool(BOT_RE.search(user_agent))


def parse_user_agent(user_agent: str, screen_width: int,
                     touch_points: int) -> tuple[str, str, str]:
    """
    Retorna ``(navegador, sistema, dispositiu)``.

    L'iPad modern s'identifica com a Mac: es distingeix per la pantalla tàctil.
    """
    browser = next((name for name, rule in BROWSER_RULES
                    if rule.search(user_agent)), "Altres")
    operating_system = next((name for name, rule in OS_RULES
                             if rule.search(user_agent)), "Altres")
    if operating_system == "macOS" and touch_points > 1:
        operating_system = "iPadOS"

    if operating_system == "iPadOS" or re.search(r"Tablet", user_agent):
        device = "Tauleta"
    elif re.search(r"Mobi|iPhone|iPod", user_agent):
        device = "Mòbil"
    elif operating_system == "Android":
        device = "Tauleta"
    elif 0 < screen_width < 768:
        device = "Mòbil"
    else:
        device = "Ordinador"
    return browser, operating_system, device


# ---------------------------------------------------------------------------
# Origen del trànsit (canal i font)
# ---------------------------------------------------------------------------
# Ordre important: els patrons més específics primer (gemini.google abans que
# google). Cada regla: (patró de domini, nom de la font, canal).
SOURCE_RULES = (
    (r"(^|\.)chatgpt\.com$|(^|\.)openai\.com$", "ChatGPT", "Assistents d'IA"),
    (r"(^|\.)perplexity\.ai$", "Perplexity", "Assistents d'IA"),
    (r"(^|\.)claude\.ai$", "Claude", "Assistents d'IA"),
    (r"^gemini\.google\.com$|^bard\.google\.com$", "Gemini", "Assistents d'IA"),
    (r"copilot\.microsoft\.com$", "Copilot", "Assistents d'IA"),
    (r"(^|\.)you\.com$|(^|\.)phind\.com$", "Altres IA", "Assistents d'IA"),
    (r"^maps\.google\.|^www\.google\.[a-z.]+/maps", "Google Maps", "Mapes"),
    (r"(^|\.)google\.[a-z.]+$", "Google", "Cerca orgànica"),
    (r"(^|\.)bing\.com$", "Bing", "Cerca orgànica"),
    (r"(^|\.)duckduckgo\.com$", "DuckDuckGo", "Cerca orgànica"),
    (r"(^|\.)yahoo\.", "Yahoo", "Cerca orgànica"),
    (r"(^|\.)ecosia\.org$", "Ecosia", "Cerca orgànica"),
    (r"(^|\.)qwant\.com$|(^|\.)startpage\.com$|(^|\.)brave\.com$",
     "Altres cercadors", "Cerca orgànica"),
    (r"(^|\.)yandex\.|(^|\.)baidu\.com$", "Altres cercadors", "Cerca orgànica"),
    (r"(^|\.)instagram\.com$", "Instagram", "Xarxes socials"),
    (r"(^|\.)facebook\.com$|(^|\.)fb\.me$", "Facebook", "Xarxes socials"),
    (r"(^|\.)linkedin\.com$|^lnkd\.in$", "LinkedIn", "Xarxes socials"),
    (r"^t\.co$|(^|\.)twitter\.com$|(^|\.)x\.com$", "X (Twitter)",
     "Xarxes socials"),
    (r"(^|\.)tiktok\.com$", "TikTok", "Xarxes socials"),
    (r"(^|\.)youtube\.com$|^youtu\.be$", "YouTube", "Xarxes socials"),
    (r"(^|\.)pinterest\.", "Pinterest", "Xarxes socials"),
    (r"(^|\.)whatsapp\.com$|^wa\.me$", "WhatsApp", "Missatgeria"),
    (r"(^|\.)telegram\.(org|me)$|^t\.me$", "Telegram", "Missatgeria"),
    (r"mail\.|outlook\.|(^|\.)gmail\.com$", "Correu web", "Correu electrònic"),
)
COMPILED_SOURCE_RULES = tuple((re.compile(pattern), source, channel)
                              for pattern, source, channel in SOURCE_RULES)
# Perquè utm_source=instagram i el referent d'Instagram comptin com la mateixa font.
KNOWN_SOURCE_NAMES = {source.lower(): source for _, source, _ in SOURCE_RULES}
KNOWN_SOURCE_NAMES.update({"ig": "Instagram", "fb": "Facebook",
                           "gmb": "Google Maps", "google_maps": "Google Maps"})

UTM_MEDIUM_CHANNELS = {
    "cpc": "Publicitat",
    "ppc": "Publicitat",
    "paid": "Publicitat",
    "paidsocial": "Publicitat",
    "display": "Publicitat",
    "email": "Correu electrònic",
    "newsletter": "Correu electrònic",
    "social": "Xarxes socials",
    "qr": "QR / Impresos",
    "print": "QR / Impresos",
}


@dataclass(frozen=True)
class TrafficSource:
    """Origen classificat d'una visita."""

    channel: str
    source: str
    referrer_host: str
    utm_source: str
    utm_medium: str
    utm_campaign: str


def classify_traffic(page_url: str, referrer: str,
                     own_hosts: set[str]) -> TrafficSource:
    """
    Classifica l'origen d'una visita segons UTM i referent.

    Example:
        >>> classify_traffic("/?utm_source=ig&utm_medium=social", "", set())
        TrafficSource(channel='Xarxes socials', source='ig', ...)
    """
    query = parse_qs(urlsplit(page_url).query)

    def first(key: str) -> str:
        return (query.get(key) or [""])[0].strip().lower()[:80]

    utm_source = first("utm_source") or first("ref")
    utm_medium = first("utm_medium")
    utm_campaign = first("utm_campaign")

    referrer_parts = urlsplit(referrer) if referrer else None
    referrer_host = (referrer_parts.hostname or "") if referrer_parts else ""
    referrer_host = referrer_host.lower().removeprefix("www.")[:120]
    if referrer_host in own_hosts:
        referrer_host = ""

    matched_source, matched_channel = "", ""
    if referrer_host:
        host_and_path = referrer_host + (referrer_parts.path if referrer_parts
                                         else "")
        for rule, source, channel in COMPILED_SOURCE_RULES:
            if rule.search(referrer_host) or rule.search(host_and_path):
                matched_source, matched_channel = source, channel
                break

    if utm_medium in UTM_MEDIUM_CHANNELS:
        channel = UTM_MEDIUM_CHANNELS[utm_medium]
    elif matched_channel:
        channel = matched_channel
    elif utm_source:
        channel = "Campanyes"
    elif referrer_host:
        channel = "Enllaços externs"
    else:
        channel = "Directe"

    source = (matched_source or KNOWN_SOURCE_NAMES.get(utm_source, utm_source)
              or referrer_host or "Directe")
    return TrafficSource(channel, source, referrer_host, utm_source,
                         utm_medium, utm_campaign)


def local_day(moment: datetime) -> str:
    """Data (AAAA-MM-DD) usada per rotar l'identificador anònim."""
    return moment.strftime("%Y-%m-%d")
