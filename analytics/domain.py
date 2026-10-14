"""Model de domini de l'analítica: esdeveniments de visita i dimensions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

# Conservació de les dades brutes (mateix criteri que Google Analytics).
RETENTION_DAYS = 760

EVENT_PAGEVIEW = "pageview"
EVENT_CONVERSION = "conversion"
EVENT_TYPES = {EVENT_PAGEVIEW, EVENT_CONVERSION}

# Dimensions per les quals es pot filtrar i agregar al tauler.
DIMENSIONS = (
    "path",
    "lang",
    "channel",
    "source",
    "referrer_host",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "country",
    "region",
    "city",
    "device",
    "browser",
    "os",
)


@dataclass
class Event:
    """
    Un esdeveniment anònim (visita de pàgina o conversió).

    ``visitor`` és un hash que rota cada dia: permet comptar visitants únics
    i reconstruir sessions sense guardar l'adreça IP ni cap identificador
    persistent al dispositiu.

    Example:
        >>> Event(event_id="ab" * 16, ts=datetime.now(timezone.utc),
        ...       type=EVENT_PAGEVIEW, visitor="f00", path="/")
    """

    event_id: str
    ts: datetime
    type: str
    visitor: str
    path: str
    name: str = ""
    lang: str = ""
    channel: str = "Directe"
    source: str = "Directe"
    referrer_host: str = ""
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    device: str = ""
    browser: str = ""
    os: str = ""
    engaged_ms: int = 0
    scroll_pct: int = 0
    expire_at: datetime = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.expire_at is None:
            self.expire_at = self.ts + timedelta(days=RETENTION_DAYS)

    def to_dict(self) -> dict:
        """Serialitza l'esdeveniment per a la capa de persistència."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """Reconstrueix un esdeveniment des de la persistència."""
        values = {}
        for key in cls.__dataclass_fields__:
            value = data.get(key)
            if key in ("ts", "expire_at"):
                values[key] = _as_utc_datetime(value)
            elif key in ("engaged_ms", "scroll_pct"):
                values[key] = int(value or 0)
            else:
                values[key] = value or ""
        return cls(**values)


def _as_utc_datetime(value: object) -> datetime | None:
    """Normalitza un valor de data (ISO o datetime) a datetime UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        raise TypeError(f"Data no vàlida: {value!r}")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
