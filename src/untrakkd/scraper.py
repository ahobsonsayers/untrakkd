"""Scrape an Untappd user's check-in history into map-ready events."""

from __future__ import annotations

import json
import os
import re
import time
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
    checkin_id: int

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
            "checkin_id": self.checkin_id,
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
        checkin_id=int(item.attrib["data-checkin-id"]),
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


_TOTAL_RE = re.compile(r'<span class="stat">(\d+)</span>\s*<span class="title">Total</span>')
_MY_PROFILE_RE = re.compile(r'href="/user/([^"]+)"[^>]*>My Profile')


def fetch_profile(session: _SyncSessionLogic) -> dict:
    """Fetch display name, total checkins, and relationship to the logged-in user."""
    page = session.get(f"{UNTAPPD_BASE}/user/{PROFILE}")
    html = page.html_content
    name = page.css("h1::text").get("").strip()
    if not name:
        m = _NAME_RE.search(html)
        name = m.group(1).strip() if m else PROFILE
    m = _TOTAL_RE.search(html)
    total = int(m.group(1)) if m else 0
    m = _MY_PROFILE_RE.search(html)
    logged_in = m.group(1) if m else ""
    return {
        "username": PROFILE,
        "display_name": name,
        "total_checkins": total,
        "is_self": logged_in == PROFILE,
        "is_friend": "Remove Friend" in html,
    }


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


_VENUE_COUNT_RE = re.compile(r"Check-ins:\s*</strong>\s*(\d+)", re.IGNORECASE)


def _is_target_user(item, profile: str) -> bool:
    for a in item.css("a[href^='/user/']"):
        href = a.attrib.get("href", "")
        if href == f"/user/{profile}" or href.startswith(f"/user/{profile}/"):
            return True
    return False


def fetch_venues(session: _SyncSessionLogic) -> list[tuple[int, int]]:
    """Return [(venue_id, expected_checkin_count), ...] from the user's venues page."""
    venues: list[tuple[int, int]] = []
    page = session.get(f"{UNTAPPD_BASE}/user/{PROFILE}/venues")
    while True:
        items = page.css("div.venue-item")
        if not items:
            break
        for v in items:
            vid = int(v.attrib["data-venue-id"])
            m = _VENUE_COUNT_RE.search(v.html_content)
            count = int(m.group(1)) if m else 0
            venues.append((vid, count))
        if len(items) < 25:
            break
        next_page = session.get(
            f"{UNTAPPD_BASE}/profile/more_venues/{PROFILE}/{len(venues)}",
            headers={"Referer": f"{UNTAPPD_BASE}/user/{PROFILE}/venues", "X-Requested-With": "XMLHttpRequest"},
        )
        if next_page.html_content.strip() in ("", "<html></html>"):
            break
        page = next_page
    return venues


def fetch_venue_checkins(
    session: _SyncSessionLogic, venue_id: int, seen: set[int], feed_filter: str
) -> list[Checkin]:
    """Page through a venue's filtered activity feed, returning target-user check-ins not in `seen`.

    feed_filter: "you" for the logged-in user's own check-ins, "friends" for friends' check-ins.
    """
    found: list[Checkin] = []
    page = session.get(f"{UNTAPPD_BASE}/venue/{venue_id}")
    slug = ""
    url = getattr(page, "url", "") or ""
    m = re.search(r"/v/([^/]+)/(\d+)", url)
    if m:
        slug = m.group(1)
    if not slug:
        return found
    referer = f"{UNTAPPD_BASE}/v/{slug}/{venue_id}/activity?filter={feed_filter}"
    page = session.get(referer)
    while True:
        items = [i for i in page.css("div.item") if i.attrib.get("data-checkin-id")]
        if not items:
            break
        for item in items:
            if feed_filter == "friends" and not _is_target_user(item, PROFILE):
                continue
            cid = int(item.attrib["data-checkin-id"])
            if cid in seen:
                continue
            seen.add(cid)
            found.append(parse_item(item))
        offset = min(int(i.attrib["data-checkin-id"]) for i in items)
        next_page = session.get(
            f"{UNTAPPD_BASE}/venue/more_feed/{venue_id}/{offset}",
            params={"filter": feed_filter, "v2": "true"},
            headers={"Referer": referer, "X-Requested-With": "XMLHttpRequest"},
        )
        if next_page.html_content.strip() in ("", "<html></html>"):
            break
        page = next_page
    return found


def main() -> None:
    if not PROFILE:
        raise SystemExit("UNTAPPD_PROFILE env var is required")
    cookie = os.environ["UNTAPPD_COOKIE"]
    with FetcherSession(impersonate="chrome", timeout=30, retries=3, headers={"Cookie": cookie}) as session:
        profile = fetch_profile(session)
        with open(_PROFILE_PATH, "w") as f:
            json.dump(profile, f, indent=2)
        seen: set[int] = set()
        checkins = fetch_checkins(session)
        seen.update(c.checkin_id for c in checkins)
        print(f"activity feed: {len(checkins)} checkins (profile total: {profile['total_checkins']})")

        history_incomplete = False

        if len(checkins) < profile["total_checkins"]:
            # Activity feed didn't return everything. Try venue fallback if we can.
            if profile["is_self"] or profile["is_friend"]:
                feed_filter = "you" if profile["is_self"] else "friends"
                print(f"venue fallback: using filter={feed_filter}")

                found_per_venue: dict[int, int] = {}
                for c in checkins:
                    if "/" in c.venue_key:
                        vid = int(c.venue_key.rsplit("/", 1)[1])
                        found_per_venue[vid] = found_per_venue.get(vid, 0) + 1

                venues = fetch_venues(session)
                to_sweep = [(vid, exp) for vid, exp in venues if exp > found_per_venue.get(vid, 0)]
                to_sweep.sort(key=lambda x: x[1], reverse=True)
                print(f"venue sweep: {len(to_sweep)}/{len(venues)} venues to sweep")
                recovered = 0
                venue_gaps = 0
                for i, (vid, expected) in enumerate(to_sweep, 1):
                    new = fetch_venue_checkins(session, vid, seen, feed_filter)
                    if new:
                        checkins.extend(new)
                        recovered += len(new)
                    found_here = found_per_venue.get(vid, 0) + len(new)
                    if found_here < expected:
                        venue_gaps += 1
                    print(f"  [{i}/{len(to_sweep)}] venue {vid}: +{len(new)} ({found_here}/{expected})")
                    time.sleep(1)
                print(f"venue sweep recovered: {recovered} checkins, {venue_gaps} venues still short")

                history_incomplete = len(checkins) < profile["total_checkins"] and venue_gaps > 0
            else:
                # Not self or friend — can't use venue fallback.
                history_incomplete = True

        profile["history_incomplete"] = history_incomplete
        with open(_PROFILE_PATH, "w") as f:
            json.dump(profile, f, indent=2)

        cache = VenueCache(_CACHE_PATH)
        events = []
        for c in sorted(checkins, key=lambda c: c.date):
            venue = cache.resolve(c.venue_key, session) if c.venue_key else None
            events.append(c.as_dict(venue))
        with open(_EVENTS_PATH, "w") as f:
            json.dump(events, f, indent=2)
        status = "INCOMPLETE" if history_incomplete else "complete"
        print(f"wrote {len(events)} checkins to {_EVENTS_PATH} ({status})")
