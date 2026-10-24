"""Shared API response helpers."""

from fastapi.responses import JSONResponse


def error_response(status_code: int, detail):
    return JSONResponse(status_code=status_code, content={"detail": detail})
