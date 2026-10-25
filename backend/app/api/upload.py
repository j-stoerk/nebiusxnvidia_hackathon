"""CSV upload endpoints."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import ROOT, get_settings
from ..services import schedule_service
from ..services.csv_validator import InputError

router = APIRouter()


@router.post("/upload")
async def upload_csv(
    sessions: UploadFile = File(...),
    prices: UploadFile | None = File(default=None),
):
    settings = get_settings()
    session_data = await sessions.read(settings.max_upload_bytes + 1)
    price_data = None
    if prices and prices.filename:
        price_data = await prices.read(settings.max_upload_bytes + 1)
    if len(session_data) > settings.max_upload_bytes or (
        price_data is not None and len(price_data) > settings.max_upload_bytes
    ):
        raise HTTPException(413, "Each CSV must be at most 2 MiB")
    try:
        return schedule_service.upload_sessions(session_data, price_data)
    except InputError as exc:
        raise HTTPException(422, detail=exc.errors) from exc


@router.post("/reset")
def reset_workspace():
    return schedule_service.reset_state()


@router.get("/sample/sessions")
def download_sample_sessions():
    path = ROOT / "data/demo/prepared/sessions.csv"
    return FileResponse(path, filename="sample_charging_sessions.csv", media_type="text/csv")


@router.get("/sample/prices")
def download_sample_prices():
    path = ROOT / "data/demo/prepared/prices.csv"
    if not path.is_file():
        raise HTTPException(404, "Sample prices not found")
    return FileResponse(path, filename="synthetic_prices_15min.csv", media_type="text/csv")
