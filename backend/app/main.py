"""Application setup and production frontend hosting; domain logic lives in services/."""

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .services.csv_validator import InputError
from .services.schedule_service import ROOT, Conflict

load_dotenv(ROOT / ".env", override=False)
app = FastAPI(title="ChargeWise AI", version="0.1.0", description="Isolated, in-memory charging simulations. Times UTC; price EUR/kWh.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])
app.include_router(router)


@app.exception_handler(InputError)
async def input_error(request: Request, exc: InputError):
    return JSONResponse(status_code=422, content={"detail": exc.errors})


@app.exception_handler(Conflict)
async def conflict(request: Request, exc: Conflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


DIST = ROOT / "frontend" / "dist"
if (DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def dashboard_not_built():
        return {"message": "Build frontend/ with npm ci and npm run build, then restart the API; or start the Vite dev server.", "api_docs": "/docs"}
