"""
Càlcul dels KPI i agregacions del tauler d'audiències.

Definicions (alineades amb GA4 perquè siguin comparables):
  - Visitant: identificador anònim diari diferent.
  - Sessió: visites d'un mateix visitant sense pauses de més de 30 minuts.
  - Sessió amb interacció: >= 10 s de temps actiu, >= 2 pàgines o conversió.
  - Taxa de rebot: 1 - (sessions amb interacció / sessions).
  - Durada de sessió: suma del temps actiu (pestanya visible) de les pàgines.
  - Conversió: enviament correcte del formulari de contacte.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import cached_property
from zoneinfo import ZoneInfo

from analytics.domain import EVENT_CONVERSION, EVENT_PAGEVIEW, Event

SESSION_GAP = timedelta(minutes=30)
ENGAGED_SESSION_MS = 10_000
BREAKDOWN_LIMIT = 100

# Dimensions que es prenen de la primera pàgina de la sessió.
SESSION_DIMENSIONS = (
    "channel", "source", "referrer_host", "utm_source", "utm_medium",
    "utm_campaign", "country", "region", "city", "device", "browser", "os",
    "lang",
)

INTERVALS = ("hour", "day", "week", "month")


@dataclass
class Session:
    """Sessió reconstruïda a partir dels esdeveniments d'un visitant."""

    visitor: str
    events: list[Event] = field(default_factory=list)

    # Valors derivats en memòria cau: només es consulten un cop la sessió ja
    # està completa (build_sessions no els llegeix mentre hi afegeix events).
    @cached_property
    def pageviews(self) -> list[Event]:
        return [event for event in self.events if event.type == EVENT_PAGEVIEW]

    @property
    def first(self) -> Event:
        return (self.pageviews or self.events)[0]

    @property
    def start(self) -> datetime:
        return self.events[0].ts

    @cached_property
    def engaged_ms(self) -> int:
        return sum(event.engaged_ms for event in self.pageviews)

    @cached_property
    def conversions(self) -> int:
        return sum(1 for event in self.events if event.type == EVENT_CONVERSION)

    @cached_property
    def is_engaged(self) -> bool:
        return (self.engaged_ms >= ENGAGED_SESSION_MS
                or len(self.pageviews) >= 2 or self.conversions > 0)


def build_sessions(events: list[Event]) -> list[Session]:
    """Agrupa els esdeveniments en sessions (pausa màxima de 30 minuts)."""
    by_visitor: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        by_visitor[event.visitor].append(event)

    sessions: list[Session] = []
    for visitor, visitor_events in by_visitor.items():
        visitor_events.sort(key=lambda event: event.ts)
        current: Session | None = None
        for event in visitor_events:
            if current is None or event.ts - current.events[-1].ts > SESSION_GAP:
                current = Session(visitor)
                sessions.append(current)
            current.events.append(event)
    sessions.sort(key=lambda session: session.start)
    return sessions


def apply_filters(events: list[Event], filters: dict[str, str]) -> list[Event]:
    """Filtra per igualtat exacta en una o més dimensions."""
    if not filters:
        return events
    return [event for event in events
            if all(getattr(event, key, None) == value
                   for key, value in filters.items())]


def compute_kpis(events: list[Event], sessions: list[Session]) -> dict:
    """Calcula els indicadors principals d'un conjunt d'esdeveniments."""
    pageviews = [event for event in events if event.type == EVENT_PAGEVIEW]
    session_count = len(sessions)
    engaged_sessions = sum(1 for session in sessions if session.is_engaged)
    converting_sessions = sum(1 for session in sessions if session.conversions)
    total_engaged_ms = sum(session.engaged_ms for session in sessions)
    pages_with_time = [event for event in pageviews if event.engaged_ms > 0]

    return {
        "visitors": len({event.visitor for event in pageviews}),
        "sessions": session_count,
        "pageviews": len(pageviews),
        "views_per_session": _ratio(len(pageviews), session_count),
        "bounce_rate": (_ratio(session_count - engaged_sessions, session_count)
                        if session_count else None),
        "avg_session_duration_s": _ratio(total_engaged_ms / 1000, session_count),
        "avg_time_on_page_s": _ratio(
            sum(event.engaged_ms for event in pages_with_time) / 1000,
            len(pages_with_time)),
        "avg_scroll_pct": _ratio(sum(event.scroll_pct for event in pageviews),
                                 len(pageviews)),
        "conversions": sum(session.conversions for session in sessions),
        "conversion_rate": (_ratio(converting_sessions, session_count)
                            if session_count else None),
    }


def breakdown_by_session_dimension(sessions: list[Session],
                                   dimension: str) -> list[dict]:
    """Agrega sessions per una dimensió d'origen, ubicació o tecnologia."""
    groups: dict[str, list[Session]] = defaultdict(list)
    for session in sessions:
        groups[getattr(session.first, dimension) or ""].append(session)

    rows = []
    for value, group in groups.items():
        session_count = len(group)
        rows.append({
            "value": value,
            "visitors": len({session.visitor for session in group}),
            "sessions": session_count,
            "pageviews": sum(len(session.pageviews) for session in group),
            "bounce_rate": _ratio(
                sum(1 for session in group if not session.is_engaged),
                session_count),
            "avg_session_duration_s": _ratio(
                sum(session.engaged_ms for session in group) / 1000,
                session_count),
            "conversions": sum(session.conversions for session in group),
            "conversion_rate": _ratio(
                sum(1 for session in group if session.conversions),
                session_count),
        })
    rows.sort(key=lambda row: (-row["visitors"], -row["sessions"], row["value"]))
    return rows[:BREAKDOWN_LIMIT]


def breakdown_pages(sessions: list[Session]) -> list[dict]:
    """Rendiment de cada pàgina: vistes, entrades, sortides, temps i scroll."""
    stats: dict[str, dict] = defaultdict(lambda: {
        "pageviews": 0, "visitors": set(), "entries": 0, "exits": 0,
        "engaged_ms": 0, "timed_views": 0, "scroll_total": 0, "conversions": 0,
    })
    for session in sessions:
        pageviews = session.pageviews
        if not pageviews:
            continue
        stats[pageviews[0].path]["entries"] += 1
        stats[pageviews[-1].path]["exits"] += 1
        for event in pageviews:
            page = stats[event.path]
            page["pageviews"] += 1
            page["visitors"].add(event.visitor)
            page["scroll_total"] += event.scroll_pct
            if event.engaged_ms:
                page["engaged_ms"] += event.engaged_ms
                page["timed_views"] += 1
        for event in session.events:
            if event.type == EVENT_CONVERSION:
                stats[event.path]["conversions"] += 1

    rows = [{
        "value": path,
        "pageviews": page["pageviews"],
        "visitors": len(page["visitors"]),
        "entries": page["entries"],
        "exits": page["exits"],
        "exit_rate": _ratio(page["exits"], page["pageviews"]),
        "avg_time_on_page_s": _ratio(page["engaged_ms"] / 1000,
                                     page["timed_views"]),
        "avg_scroll_pct": _ratio(page["scroll_total"], page["pageviews"]),
        "conversions": page["conversions"],
    } for path, page in stats.items() if page["pageviews"]]
    rows.sort(key=lambda row: (-row["pageviews"], row["value"]))
    return rows[:BREAKDOWN_LIMIT]


def pick_interval(start: date, end: date, requested: str) -> str:
    """Tria la granularitat temporal (``auto`` la decideix pel rang)."""
    days = (end - start).days
    if requested == "hour" and days > 31:
        return "day"
    if requested in INTERVALS:
        return requested
    if days <= 2:
        return "hour"
    if days <= 92:
        return "day"
    if days <= 400:
        return "week"
    return "month"


def _bucket_start(moment: datetime, interval: str) -> datetime:
    if interval == "hour":
        return moment.replace(minute=0, second=0, microsecond=0)
    day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    if interval == "day":
        return day
    if interval == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _next_bucket(moment: datetime, interval: str) -> datetime:
    if interval == "hour":
        return moment + timedelta(hours=1)
    if interval == "day":
        return moment + timedelta(days=1)
    if interval == "week":
        return moment + timedelta(days=7)
    year, month = (moment.year + 1, 1) if moment.month == 12 else (
        moment.year, moment.month + 1)
    return moment.replace(year=year, month=month)


def build_timeseries(sessions: list[Session], start: datetime, end: datetime,
                     interval: str, tz: ZoneInfo) -> list[dict]:
    """Sèrie temporal amb tots els trams (també els buits)."""
    buckets: dict[datetime, list[Session]] = defaultdict(list)
    visitors: dict[datetime, set[str]] = defaultdict(set)
    pageviews: Counter = Counter()
    for session in sessions:
        bucket = _bucket_start(session.start.astimezone(tz), interval)
        buckets[bucket].append(session)
        for event in session.pageviews:
            event_bucket = _bucket_start(event.ts.astimezone(tz), interval)
            visitors[event_bucket].add(event.visitor)
            pageviews[event_bucket] += 1

    series = []
    cursor = _bucket_start(start.astimezone(tz), interval)
    local_end = end.astimezone(tz)
    while cursor < local_end:
        group = buckets.get(cursor, [])
        series.append({
            "t": cursor.isoformat(),
            "visitors": len(visitors.get(cursor, ())),
            "sessions": len(group),
            "pageviews": pageviews.get(cursor, 0),
            "conversions": sum(session.conversions for session in group),
            "bounce_rate": _ratio(
                sum(1 for session in group if not session.is_engaged),
                len(group)),
        })
        # Naive + localize per travessar correctament els canvis d'hora.
        cursor = _next_bucket(cursor.replace(tzinfo=None), interval)
        cursor = cursor.replace(tzinfo=tz)
    return series


def build_heatmap(sessions: list[Session], tz: ZoneInfo) -> list[list[int]]:
    """Matriu 7×24 (dilluns=0) de sessions per dia de la setmana i hora."""
    matrix = [[0] * 24 for _ in range(7)]
    for session in sessions:
        local_start = session.start.astimezone(tz)
        matrix[local_start.weekday()][local_start.hour] += 1
    return matrix


def build_report(current_events: list[Event], previous_events: list[Event],
                 start: datetime, end: datetime, interval: str,
                 filters: dict[str, str], tz: ZoneInfo) -> dict:
    """
    Construeix l'informe complet del tauler per a un rang i uns filtres.

    ``previous_events`` correspon al període immediatament anterior de la
    mateixa durada i serveix per calcular les variacions.
    """
    current = apply_filters(current_events, filters)
    previous = apply_filters(previous_events, filters)
    current_sessions = build_sessions(current)
    previous_sessions = build_sessions(previous)
    previous_start = start - (end - start)

    return {
        "kpis": {
            "current": compute_kpis(current, current_sessions),
            "previous": compute_kpis(previous, previous_sessions),
        },
        "timeseries": build_timeseries(current_sessions, start, end, interval,
                                       tz),
        "previous_timeseries": build_timeseries(previous_sessions,
                                                previous_start, start,
                                                interval, tz),
        "pages": breakdown_pages(current_sessions),
        "entry_pages": breakdown_by_entry(current_sessions),
        "breakdowns": {
            dimension: breakdown_by_session_dimension(current_sessions,
                                                      dimension)
            for dimension in SESSION_DIMENSIONS
        },
        "heatmap": build_heatmap(current_sessions, tz),
    }


def breakdown_by_entry(sessions: list[Session]) -> list[dict]:
    """Pàgines d'entrada (on aterra la gent) amb el seu rebot i conversió."""
    groups: dict[str, list[Session]] = defaultdict(list)
    for session in sessions:
        if session.pageviews:
            groups[session.pageviews[0].path].append(session)
    rows = [{
        "value": path,
        "sessions": len(group),
        "bounce_rate": _ratio(sum(1 for s in group if not s.is_engaged),
                              len(group)),
        "conversions": sum(s.conversions for s in group),
    } for path, group in groups.items()]
    rows.sort(key=lambda row: (-row["sessions"], row["value"]))
    return rows[:BREAKDOWN_LIMIT]


def realtime_summary(events: list[Event], now: datetime) -> dict:
    """Visitants actius als últims 5 minuts i pàgines que estan mirant."""
    threshold = now - timedelta(minutes=5)
    recent = [event for event in events
              if event.ts >= threshold and event.type == EVENT_PAGEVIEW]
    latest_by_visitor: dict[str, Event] = {}
    for event in sorted(recent, key=lambda event: event.ts):
        latest_by_visitor[event.visitor] = event
    pages = Counter(event.path for event in latest_by_visitor.values())
    countries = Counter(event.country for event in latest_by_visitor.values())
    return {
        "active_visitors": len(latest_by_visitor),
        "pages": [{"value": path, "visitors": count}
                  for path, count in pages.most_common(10)],
        "countries": [{"value": code, "visitors": count}
                      for code, count in countries.most_common(10)],
        "generated_at": now.astimezone(timezone.utc).isoformat(),
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, 4)
