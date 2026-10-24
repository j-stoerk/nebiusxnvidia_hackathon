"""ChargeWise AI FastAPI entrypoint."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import ROOT, get_settings
from .services.csv_validator import InputError
from .services import schedule_service

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Simulated EV charging optimization. Times UTC; prices EUR/kWh. In-memory MVP.",
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
    allow_headers=["Content-Type"],
)
app.include_router(api_router)


@app.on_event("startup")
def startup():
    schedule_service.load_demo_if_empty()


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
