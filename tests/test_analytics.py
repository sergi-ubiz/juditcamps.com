"""Proves de l'analítica d'audiències (domini, enriquiment, informes i API)."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analytics.domain import Event  # noqa: E402
from analytics.enrich import (NullGeoLocator, classify_traffic,  # noqa: E402
                              is_bot, parse_user_agent)
from analytics.report import (build_report, build_sessions,  # noqa: E402
                              compute_kpis)
from analytics.routes import (AnalyticsConfig,  # noqa: E402
                              create_analytics_blueprint, normalize_path)
from analytics.store import SqliteEventStore  # noqa: E402

TOKEN = "t" * 40
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
             "Mobile/15E148 Safari/604.1")
CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


def make_event(visitor: str, minutes: int, **overrides) -> Event:
    base = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    values = {"event_id": f"{visitor}{minutes}".ljust(32, "0")[:32],
              "ts": base + timedelta(minutes=minutes), "type": "pageview",
              "visitor": visitor, "path": "/"}
    values.update(overrides)
    return Event(**values)


def test_sessions_split_after_30_minutes_of_inactivity():
    events = [make_event("a", 0), make_event("a", 10), make_event("a", 50)]
    sessions = build_sessions(events)
    assert [len(session.events) for session in sessions] == [2, 1]


def test_kpis_bounce_and_conversion():
    events = [
        make_event("a", 0, engaged_ms=3000),                     # rebot
        make_event("b", 0, engaged_ms=20000),                    # interacció
        make_event("c", 0), make_event("c", 1, path="/es/"),     # 2 pàgines
        make_event("c", 2, type="conversion", name="contact_submit"),
    ]
    kpis = compute_kpis(events, build_sessions(events))
    assert kpis["visitors"] == 3
    assert kpis["sessions"] == 3
    assert kpis["pageviews"] == 4
    assert kpis["bounce_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert kpis["conversions"] == 1


def test_report_filters_and_timeseries():
    events = [make_event("a", 0, country="ES"), make_event("b", 0, country="FR")]
    start = datetime(2026, 10, 1, tzinfo=ZoneInfo("Europe/Madrid"))
    report = build_report(events, [], start, start + timedelta(days=2), "day",
                          {"country": "ES"}, ZoneInfo("Europe/Madrid"))
    assert report["kpis"]["current"]["visitors"] == 1
    assert len(report["timeseries"]) == 2
    assert report["breakdowns"]["country"][0]["value"] == "ES"


@pytest.mark.parametrize("referrer, url, expected", [
    ("https://www.google.com/", "/", ("Cerca orgànica", "Google")),
    ("https://chatgpt.com/", "/", ("Assistents d'IA", "ChatGPT")),
    ("https://l.instagram.com/", "/", ("Xarxes socials", "Instagram")),
    ("", "/?utm_source=flyer&utm_medium=qr", ("QR / Impresos", "flyer")),
    ("", "/?utm_source=ig&utm_medium=social", ("Xarxes socials", "Instagram")),
    ("https://juditcamps.com/es/", "/", ("Directe", "Directe")),
    ("https://elcaliu.cat/article", "/", ("Enllaços externs", "elcaliu.cat")),
])
def test_traffic_classification(referrer, url, expected):
    traffic = classify_traffic(url, referrer, {"juditcamps.com"})
    assert (traffic.channel, traffic.source) == expected


def test_user_agent_parsing_and_bots():
    assert parse_user_agent(IPHONE_UA, 390, 5) == ("Safari", "iOS", "Mòbil")
    assert parse_user_agent(CHROME_UA, 1920, 0) == ("Chrome", "Windows",
                                                    "Ordinador")
    assert is_bot("Googlebot/2.1") and is_bot("")
    assert not is_bot(CHROME_UA)


def test_normalize_path():
    assert normalize_path("/index.html?utm_source=x") == "/"
    assert normalize_path("/es/index.html") == "/es/"
    assert normalize_path("/privadesa.html#drets") == "/privadesa"


@pytest.fixture()
def client(tmp_path):
    app = Flask(__name__)
    store = SqliteEventStore(str(tmp_path / "events.sqlite3"))
    config = AnalyticsConfig(dashboard_token=TOKEN, salt="salt",
                             own_hosts={"localhost"})
    app.register_blueprint(create_analytics_blueprint(store, NullGeoLocator(),
                                                      config))
    return app.test_client()


def post_event(client, payload, user_agent=CHROME_UA):
    return client.post("/api/pulse", data=json.dumps(payload),
                       content_type="text/plain",
                       headers={"User-Agent": user_agent})


def test_collect_and_report_end_to_end(client):
    page_id = "a" * 32
    assert post_event(client, {"t": "pageview", "id": page_id, "u": "/",
                               "r": "https://www.google.com/", "l": "ca",
                               "sw": 1920}).status_code == 204
    assert post_event(client, {"t": "engagement", "id": page_id, "e": 15000,
                               "s": 80}).status_code == 204
    assert post_event(client, {"t": "conversion", "id": "b" * 32,
                               "n": "contact_submit", "u": "/"}).status_code == 204
    # Els robots s'ignoren en silenci.
    post_event(client, {"t": "pageview", "id": "c" * 32, "u": "/"}, "Googlebot")

    body = client.get(f"/stats/{TOKEN}/report").get_json()
    kpis = body["kpis"]["current"]
    assert kpis["pageviews"] == 1
    assert kpis["conversions"] == 1
    assert kpis["bounce_rate"] == 0
    assert body["pages"][0]["avg_scroll_pct"] == 80
    assert body["breakdowns"]["channel"][0]["value"] == "Cerca orgànica"


def test_dashboard_requires_valid_token(client):
    assert client.get("/stats/incorrecte/").status_code == 404
    assert client.get("/stats/incorrecte/report").status_code == 404
    response = client.get(f"/stats/{TOKEN}/")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_collect_rejects_foreign_origin_and_bad_ids(client):
    foreign = client.post("/api/pulse", data=json.dumps({"t": "pageview",
                                                         "id": "d" * 32}),
                          headers={"Origin": "https://evil.example",
                                   "User-Agent": CHROME_UA})
    assert foreign.status_code == 403
    assert post_event(client, {"t": "pageview", "id": "nope"}).status_code == 400
    assert post_event(client, {"t": "conversion", "id": "e" * 32,
                               "n": "fake"}).status_code == 400
