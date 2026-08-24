"""Scrape an Untappd user's check-in history into map-ready events."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

from scrapling.engines.static import _SyncSessionLogic
from scrapling.fetchers import FetcherSession

UNTAPPD_BASE = "https://untappd.com"
PROFILE = os.environ.get("UNTAPPD_PROFILE", "")
PER_PAGE = 25
MAX_PAGES = 50

_NEAR_RE = re.compile(r"near=(-?\d+\.\d+),(-?\d+\.\d+)")
_TITLE_RE = re.compile(r"<title>(?:.*?) - ([^<]+) - Untappd</title>")
_NAME_RE = re.compile(r'<h1 class="[^"]*name[^"]*"[^>]*>([^<]+)</h1>')

_DATA_DIR = os.environ.get("UNTRAKKD_DATA", "data")
os.makedirs(_DATA_DIR, exist_ok=True)
_CACHE_PATH = os.environ.get("UNTRAKKD_CACHE", os.path.join(_DATA_DIR, "venue_cache.json"))
_EVENTS_PATH = os.environ.get("UNTRAKKD_EVENTS", os.path.join(_DATA_DIR, "events.json"))
_PROFILE_PATH = os.environ.get("UNTRAKKD_PROFILE_CACHE", os.path.join(_DATA_DIR, "profile.json"))


@dataclass
class Checkin:
    beer: str
    brewery: str
    venue_key: str  # "slug/id" from /v/ href
    date: datetime
    rating: float | None

    def as_dict(self, venue: Venue | None) -> dict:
        return {
            "beer": self.beer,
            "brewery": self.brewery,
            "venue": venue.name if venue else None,
            "city": venue.city if venue else None,
            "lat": venue.lat if venue else None,
            "lng": venue.lng if venue else None,
            "date": self.date.isoformat(),
            "rating": self.rating,
        }


@dataclass
class Venue:
    name: str
    city: str
    lat: float
    lng: float


def parse_item_datetime(raw: str) -> datetime:
    # untappd: "Fri, 21 Aug 2026 20:03:27 +0000"
    return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %z")


def parse_item(item) -> Checkin:
    links = item.css("p.text a")
    beer = links[1].text.strip()
    brewery = links[2].text.strip()
    venue_href = ""
    for a in item.css("a[href^='/v/']"):
        venue_href = a.attrib.get("href", "")
        break
    date_raw = item.css("a.time::text").get("")
    rating_raw = item.css("div.caps::attr(data-rating)").get("")
    return Checkin(
        beer=beer,
        brewery=brewery,
        venue_key=venue_href.split("/v/", 1)[1] if venue_href else "",
        date=parse_item_datetime(date_raw),
        rating=float(rating_raw) if rating_raw else None,
    )


class VenueCache:
    """Resolve venue name/coords from venue pages, cached to disk."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._data: dict[str, Venue] = {}
        if os.path.exists(path):
            with open(path) as f:
                for k, v in json.load(f).items():
                    self._data[k] = Venue(**v)

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump({k: v.__dict__ for k, v in self._data.items()}, f, indent=2)

    def resolve(self, key: str, session: _SyncSessionLogic) -> Venue | None:
        if key in self._data:
            return self._data[key]
        venue = self._fetch(key, session)
        if venue is not None:
            self._data[key] = venue
            self.save()
        return venue

    def _fetch(self, key: str, session: _SyncSessionLogic) -> Venue | None:
        try:
            page = session.get(f"{UNTAPPD_BASE}/v/{key}")
        except Exception:  # noqa: BLE001 - untappd is flaky; a venue is optional anyway
            return None
        m = _NEAR_RE.search(page.html_content)
        if not m:
            return None
        name = page.css("h1::text").get("") or ""
        tm = _TITLE_RE.search(page.html_content)
        city = tm.group(1) if tm else ""
        return Venue(name=name, city=city, lat=float(m.group(1)), lng=float(m.group(2)))


def fetch_profile(session: _SyncSessionLogic) -> dict:
    """Fetch display name from the user's profile page."""
    page = session.get(f"{UNTAPPD_BASE}/user/{PROFILE}")
    name = page.css("h1::text").get("").strip()
    if not name:
        m = _NAME_RE.search(page.html_content)
        name = m.group(1).strip() if m else PROFILE
    return {"username": PROFILE, "display_name": name}


def fetch_checkins(session: _SyncSessionLogic) -> list[Checkin]:
    seen: set[int] = set()
    checkins: list[Checkin] = []
    page = session.get(f"{UNTAPPD_BASE}/user/{PROFILE}/checkins")
    items = [i for i in page.css("div.item") if i.attrib.get("data-checkin-id")]
    for item in items:
        cid = int(item.attrib["data-checkin-id"])
        if cid not in seen:
            seen.add(cid)
            checkins.append(parse_item(item))
    if not items:
        return checkins
    offset = min(int(i.attrib["data-checkin-id"]) for i in items)
    while True:
        page = session.get(
            f"{UNTAPPD_BASE}/profile/more_feed/{PROFILE}/{offset}",
            params={"v2": "true"},
            headers={"Referer": f"{UNTAPPD_BASE}/user/{PROFILE}/checkins", "X-Requested-With": "XMLHttpRequest"},
        )
        items = [i for i in page.css("div.item") if i.attrib.get("data-checkin-id")]
        if not items:
            break
        new = 0
        for item in items:
            cid = int(item.attrib["data-checkin-id"])
            if cid not in seen:
                seen.add(cid)
                checkins.append(parse_item(item))
                new += 1
        if new == 0:
            break
        offset = min(int(i.attrib["data-checkin-id"]) for i in items)
        if len(checkins) >= MAX_PAGES * PER_PAGE:
            break
    return checkins


def main() -> None:
    if not PROFILE:
        raise SystemExit("UNTAPPD_PROFILE env var is required")
    cookie = os.environ["UNTAPPD_COOKIE"]
    with FetcherSession(impersonate="chrome", timeout=30, retries=3, headers={"Cookie": cookie}) as session:
        profile = fetch_profile(session)
        with open(_PROFILE_PATH, "w") as f:
            json.dump(profile, f, indent=2)
        checkins = fetch_checkins(session)
        cache = VenueCache(_CACHE_PATH)
        events = []
        for c in checkins:
            venue = cache.resolve(c.venue_key, session) if c.venue_key else None
            events.append(c.as_dict(venue))
        with open(_EVENTS_PATH, "w") as f:
            json.dump(events, f, indent=2)
        print(f"wrote {len(events)} checkins to {_EVENTS_PATH}")
