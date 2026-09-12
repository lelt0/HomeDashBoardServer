from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from home_dashboard.dashboard.layout import load_layout

BASE_DIR = Path(__file__).resolve().parents[2]

app = FastAPI(title="Home Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")


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
    titles = {
        "interaction": "タッチ操作",
        "placeholder": "Home Dashboard",
    }
    title = titles.get(feature)
    if title is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Feature not found")

    return templates.TemplateResponse(
        request=request,
        name="pages/feature.html",
        context={"title": title, "feature": feature},
    )
