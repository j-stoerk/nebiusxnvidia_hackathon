"""CSV validation for charging sessions and electricity prices."""

import csv
import io

import pandas as pd
from pydantic import ValidationError

from ..config import get_settings
from ..models import PricePoint, VehicleSession

REQUIRED_COLUMNS = {
    "vehicle_id",
    "arrival_time",
    "departure_time",
    "energy_required_kwh",
    "max_charging_power_kw",
}
OPTIONAL_COLUMNS = {
    "charger_id",
    "battery_capacity_kwh",
    "initial_soc",
    "requested_soc",
}


class InputError(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [{"message": str(errors)}]
        super().__init__(self.errors[0]["message"])


def _frame(content: bytes) -> pd.DataFrame:
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise InputError("CSV exceeds the 2 MiB limit")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text), strict=True)
        header = next(reader, [])
        if not header:
            raise InputError("Expected a nonempty UTF-8 CSV")
        if len(header) != len(set(header)):
            raise InputError("Duplicate CSV columns")
        return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (UnicodeDecodeError, csv.Error, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InputError("Expected a nonempty UTF-8 CSV with consistent columns") from exc


def validate_sessions_csv(content: bytes) -> list[VehicleSession]:
    frame = _frame(content)
    missing = REQUIRED_COLUMNS - set(frame.columns)
    unknown = set(frame.columns) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
    if missing or unknown:
        raise InputError(
            f"Missing columns: {', '.join(sorted(missing)) or 'none'}; "
            f"unsupported columns: {', '.join(sorted(unknown)) or 'none'}"
        )
    if not 1 <= len(frame) <= 100:
        raise InputError("Upload must contain between 1 and 100 sessions")

    errors, sessions, seen = [], [], set()
    for number, row in enumerate(frame.to_dict("records"), start=2):
        try:
            payload = {k: v for k, v in row.items() if v != ""}
            session = VehicleSession.model_validate(payload)
            if session.vehicle_id in seen:
                errors.append({"row": number, "column": "vehicle_id", "message": "Duplicate vehicle_id"})
            seen.add(session.vehicle_id)
            sessions.append(session)
        except ValidationError as exc:
            errors.extend(
                {"row": number, "column": ".".join(map(str, err["loc"])), "message": err["msg"]}
                for err in exc.errors()
            )
    if errors:
        raise InputError(errors[:100])
    return sessions


def validate_prices_csv(content: bytes) -> list[PricePoint]:
    frame = _frame(content)
    if set(frame.columns) != {"timestamp", "price_eur_per_kwh"}:
        raise InputError("Price CSV requires timestamp,price_eur_per_kwh")
    if not 1 <= len(frame) <= 2000:
        raise InputError("Price CSV must contain between 1 and 2000 rows")
    prices = []
    for number, row in enumerate(frame.to_dict("records"), start=2):
        try:
            prices.append(PricePoint.model_validate(row))
        except ValidationError as exc:
            raise InputError([{"row": number, "message": e["msg"]} for e in exc.errors()]) from exc
    if len({p.timestamp for p in prices}) != len(prices):
        raise InputError("Duplicate price timestamps")
    return sorted(prices, key=lambda p: p.timestamp)
