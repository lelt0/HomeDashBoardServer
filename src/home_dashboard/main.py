from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from home_dashboard.dashboard.layout import load_layout
from home_dashboard.features.registry import get_feature
from home_dashboard.features.trash import TRASH_CONFIG_PATH, load_trash_calendar

BASE_DIR = Path(__file__).resolve().parents[2]

app = FastAPI(title="Home Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    now = datetime.now()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "layout": load_layout(),
            "trash_calendar": load_trash_calendar(now, TRASH_CONFIG_PATH),
        },
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/page/{feature}", response_class=HTMLResponse)
async def feature_page(request: Request, feature: str) -> HTMLResponse:
    try:
        definition = get_feature(feature)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Feature not found") from exc

    if definition.page_template is None:
        raise HTTPException(status_code=404, detail="Feature page not available")

    return templates.TemplateResponse(
        request=request,
        name=definition.page_template,
        context={"title": definition.title, "feature": feature},
    )
