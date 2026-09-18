from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from home_dashboard.dashboard.layout import load_layout
from home_dashboard.features.registry import FEATURES, get_feature

BASE_DIR = Path(__file__).resolve().parents[2]

app = FastAPI(title="Home Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")

for definition in FEATURES.values():
    if definition.router is not None:
        app.include_router(definition.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"layout": load_layout()},
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
