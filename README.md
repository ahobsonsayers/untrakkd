# untrakkd

Show any Untappd user's check-in history on an interactive map with a timeline sidebar. Pins show what they drank, where, and when — with dotted route lines connecting consecutive check-ins, star ratings, and live stats.

This started as a joke when I told one of my friends I'd be able to track where he was in the world based on his Untappd check-ins. He checks in a LOT 😂

Built with [FastAPI](https://fastapi.tiangolo.com/), [Scrapling](https://github.com/D4Vinci/Scrapling), and [MapLibre GL JS](https://maplibre.org/).

## Features

- **Interactive map** — every check-in as a pin with glow halo, dotted route lines with directional chevrons between consecutive check-ins
- **Timeline sidebar** — newest-first cards with date, location, drink, venue, and star ratings
- **Live stats** — drinks per week, average rating, top venue, top location
- **Scroll-to-fly** — scrolling the timeline flies the map to each check-in
- **Auto-refresh** — fetches on startup and every hour
- **Docker-ready** — one compose command to run

## How it works

1. `untrakkd fetch` scrapes a user's check-in history from Untappd using cookies you supply, paginating through the activity feed via the `more_feed` endpoint.
2. The profile page is fetched to get the display name, total check-in count, and whether the target user is you or a friend.
3. If the activity feed returns fewer check-ins than the profile reports:
   - If the target is **you** (logged-in user) or a **friend**, the scraper visits the user's Places page (`/user/{name}/venues`) to find all venues with a check-in count that doesn't match what the activity feed already collected.
   - For each mismatched venue, it paginates the venue's activity feed filtered to **"You"** (if scraping yourself) or **"Friends"** (if scraping a friend). This recovers check-ins that the activity feed capped.
   - The friends filter works because it shows only friends' check-ins at that venue — much lower volume than the "all users" feed, so it pages further back.
4. If any venue still shows fewer check-ins than expected after the sweep, `history_incomplete` is set in `data/profile.json` and the UI shows "Full check-in history could not be fetched" at the bottom of the timeline.
5. If the target is neither you nor a friend, the venue fallback is skipped entirely and the incomplete notice shows if the activity feed was short.
6. For each unique venue, the venue page is visited to grab coordinates and city, cached on disk.
7. Everything is written to `data/events.json`.
8. `untrakkd serve` runs a FastAPI server that renders the data as MapLibre pins plus a timeline sidebar.

### Why the venue fallback is needed

Untappd caps the activity feed (`more_feed` endpoint) for other users' profiles. For your own account it pages fully, but for anyone else it stops after a few hundred check-ins. The venue fallback recovers the rest by paginating each venue's friends-filtered feed, which has far lower volume. It may not recover everything — check-ins at high-traffic venues before a friendship started won't appear in the friends feed. Those gaps trigger the incomplete notice.

If you're not friends with the target user, the venue fallback is unavailable — you'll only get the check-ins the activity feed returns (capped at a few hundred recent ones). Add the user as a friend on Untappd to enable full history recovery.

## Getting your Untappd cookie

You need a cookie from a logged-in Untappd session — the scraper uses it to access the check-in feed (which requires authentication).

1. Open [untappd.com](https://untappd.com) and log in.
2. Open your browser's DevTools (F12) → **Network** tab.
3. Refresh the page, click any request to `untappd.com`, and find the **Request Headers**.
4. Copy the full value of the `Cookie:` header. It'll be a long string of `key=value; key=value; ...` pairs.

You also need the target user's username slug — the part after `/user/` in their profile URL (e.g. `someuser` for `untappd.com/user/someuser`).

## Run with Docker (recommended)

```bash
export UNTAPPD_COOKIE="..."
export UNTAPPD_PROFILE="username"
task run:docker
```

Then open http://localhost:8000.

Data is persisted to `./data` via a volume. The server fetches on startup and every hour. Run `docker compose exec untrakkd untrakkd fetch` to refresh manually.

## Run locally

```bash
task install
export UNTAPPD_COOKIE="..."
export UNTAPPD_PROFILE="username"
task run:server
```

Then open http://localhost:8000. The server fetches on startup and every hour.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `UNTAPPD_PROFILE` | _(required)_ | Untappd username slug |
| `UNTAPPD_COOKIE` | _(required)_ | Cookie header from a logged-in session |
| `UNTRAKKD_FETCH_INTERVAL` | `3600` | Background fetch interval in seconds |
| `UNTRAKKD_DATA` | `data` | Data directory path |
| `UNTRAKKD_EVENTS` | `data/events.json` | Events output path |
| `UNTRAKKD_CACHE` | `data/venue_cache.json` | Venue cache path |
| `UNTRAKKD_PROFILE_CACHE` | `data/profile.json` | Profile cache path |

Changing `UNTAPPD_PROFILE` will overwrite the data on the next fetch.

## Disclaimer

This project was almost entirely made using a coding agent for fun. It was made quickly with minimal review, so do not expect this to be production ready like any of my other projects. YMMV. Have fun!