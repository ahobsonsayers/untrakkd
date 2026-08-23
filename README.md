# ***tracker

A silly toy app that maps where *** has drunk beer around the world, plus a world timeline of every check-in. Built with [FastAPI](https://fastapi.tiangolo.com/), [Scrapling](https://github.com/D4Vinci/Scrapling) (light HTTP scraping), and [MapLibre GL JS](https://maplibre.org/).

Not production-ready — a toy, built fast.

## How it works

1. `***tracker fetch` scrapes ***'s full check-in history from Untappd using the cookies you supply, paginating through all ~469 check-ins.
2. For each unique venue it visits the venue page to grab coordinates and city from the (public) Google Maps link and `<title>` tag, cached on disk.
3. Everything is written to `data/events.json`.
4. `***tracker serve` runs a FastAPI server that renders `data/events.json` as MapLibre pins (each showing what he drank, the brewery, and the date) plus a timeline sidebar.

## Setup

```bash
task install
```

You need a logged-in Untappd cookie. Open untappd.com in your browser, copy the `Cookie` header value, and export it:

```bash
export UNTAPPD_COOKIE="..."
```

## Fetch the data

```bash
task run -- fetch
```

This writes `data/events.json` and `data/venue_cache.json`.

## Run the server

```bash
task run:server
```

Then open http://localhost:8000.

On startup the server runs a fetch automatically, then re-fetches every hour. Set `***_FETCH_INTERVAL` (seconds) to override the interval.

## Docker

```bash
export UNTAPPD_COOKIE="..."   # passed to the container via compose
task run:docker
```

Data is persisted to `./data` via a volume. Run `docker compose exec ***tracker ***tracker fetch` to refresh it, or trigger it inside the container.
