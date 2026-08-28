import json
import logging
import os
import threading
import traceback

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .scraper import main as scrape

log = logging.getLogger("untrakkd")

_FETCH_INTERVAL = int(os.environ.get("UNTRAKKD_FETCH_INTERVAL", "3600"))

app = FastAPI(title="untrakkd")


def _run_fetch() -> None:
    log.info("fetch starting")
    try:
        scrape()
    except Exception:  # noqa: BLE001 - background fetch must not kill the server
        log.error("fetch failed:\n%s", traceback.format_exc())


def _schedule_fetch() -> None:
    _run_fetch()
    timer = threading.Timer(_FETCH_INTERVAL, _schedule_fetch)
    timer.daemon = True
    timer.start()


@app.on_event("startup")
def _start_fetch_loop() -> None:
    thread = threading.Thread(target=_schedule_fetch, daemon=True)
    thread.start()


_DATA_DIR = os.environ.get("UNTRAKKD_DATA", os.path.join("data", ""))
_EVENTS_PATH = os.environ.get("UNTRAKKD_EVENTS", os.path.join(_DATA_DIR, "events.json"))
_PROFILE_PATH = os.environ.get("UNTRAKKD_PROFILE_CACHE", os.path.join(_DATA_DIR, "profile.json"))
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def load_events() -> list[dict]:
    try:
        with open(_EVENTS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_profile() -> dict:
    try:
        with open(_PROFILE_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {
        "total_checkins": data.get("total_checkins", 0),
        "history_incomplete": data.get("history_incomplete", False),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
def events() -> list[dict]:
    return load_events()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "events": json.dumps(load_events()),
            "profile": json.dumps(load_profile()),
        },
    )
