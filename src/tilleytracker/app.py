import json
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI(title="***tracker")

_EVENTS_PATH = os.environ.get("***_EVENTS", os.path.join("data", "events.json"))
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def load_events() -> list[dict]:
    try:
        with open(_EVENTS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


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
        context={"request": request, "events": json.dumps(load_events())},
    )
