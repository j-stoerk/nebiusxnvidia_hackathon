"""ChargeWise AI FastAPI entrypoint."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import ROOT, get_settings
from .services.csv_validator import InputError
from .services import schedule_service
from uuid import uuid4
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_):
    schedule_service.load_demo_if_empty()
    yield

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Simulated EV charging optimization. Times UTC; prices EUR/kWh. In-memory MVP.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "If-Match"],
)
app.include_router(api_router)


@app.middleware("http")
async def simulation_workspace(request: Request, call_next):
    key = request.cookies.get("chargewise_workspace", "")
    if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
        key = uuid4().hex
    workspace = schedule_service.WORKSPACE.set(key)
    pinned = schedule_service.CURRENT_STATE.set(None)
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        schedule_service.CURRENT_STATE.set(schedule_service.current_state())
    raw_version = request.headers.get("If-Match")
    version = schedule_service.EXPECTED_VERSION.set(int(raw_version) if raw_version and raw_version.isdigit() else None)
    try:
        response = await call_next(request)
        response.set_cookie("chargewise_workspace", key, httponly=True, samesite="strict", secure=request.url.scheme == "https")
        return response
    finally:
        schedule_service.EXPECTED_VERSION.reset(version)
        schedule_service.CURRENT_STATE.reset(pinned)
        schedule_service.WORKSPACE.reset(workspace)


@app.exception_handler(schedule_service.Conflict)
async def state_conflict(_: Request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InputError)
async def input_error_handler(_: Request, exc: InputError):
    return JSONResponse(status_code=422, content={"detail": exc.errors})


DIST = ROOT / "frontend" / "dist"
if (DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(DIST / "index.html")
else:

    @app.get("/", include_in_schema=False)
    def dashboard_not_built():
        return {
            "message": "Build frontend with npm install && npm run build, or start the Vite dev server.",
            "api_docs": "/docs",
        }
