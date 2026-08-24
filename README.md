# untrakkd

Map any Untappd user's check-in history on an interactive map with a timeline sidebar. Pins show what they drank, where, and when — with dotted route lines connecting consecutive check-ins, star ratings, and live stats.

Built with [FastAPI](https://fastapi.tiangolo.com/), [Scrapling](https://github.com/D4Vinci/Scrapling), and [MapLibre GL JS](https://maplibre.org/).

## Features

- **Interactive map** — every check-in as a pin with glow halo, dotted route lines with directional chevrons between consecutive check-ins
- **Timeline sidebar** — newest-first cards with date, location, drink, venue, and star ratings
- **Live stats** — drinks per week, average rating, top venue, top location
- **Scroll-to-fly** — scrolling the timeline flies the map to each check-in
- **Auto-refresh** — fetches on startup and every hour
- **Docker-ready** — one compose command to run

## How it works

1. `untrakkd fetch` scrapes a user's full check-in history from Untappd using cookies you supply, paginating through all available check-ins via the `more_feed` endpoint.
2. The user's display name is fetched from their profile page and saved to `data/profile.json`.
3. For each unique venue it visits the venue page to grab coordinates and city from the (public) Google Maps link and `<title>` tag, cached on disk.
4. Everything is written to `data/events.json`.
5. `untrakkd serve` runs a FastAPI server that renders the data as MapLibre pins plus a timeline sidebar.

## Setup

```bash
task install
```

You need:

1. A logged-in Untappd cookie. Open untappd.com in your browser, copy the `Cookie` header value.
2. The Untappd username (the slug in the profile URL, e.g. `someuser` for `untappd.com/user/someuser`).

```bash
export UNTAPPD_COOKIE="..."
export UNTAPPD_PROFILE="username"
```

## Fetch the data

```bash
task run -- fetch
```

This writes `data/events.json`, `data/venue_cache.json`, and `data/profile.json`.

## Run the server

```bash
task run:server
```

Then open http://localhost:8000.

On startup the server runs a fetch automatically, then re-fetches every hour. Set `UNTRAKKD_FETCH_INTERVAL` (seconds) to override the interval.

## Docker

```bash
export UNTAPPD_COOKIE="..."
export UNTAPPD_PROFILE="username"
task run:docker
```

Data is persisted to `./data` via a volume. Run `docker compose exec untrakkd untrakkd fetch` to refresh it manually.

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