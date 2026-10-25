"""CSV validation for charging sessions and electricity prices."""

import csv
import io
from datetime import timedelta

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
    "connector_type",
    "transition_soc",
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
        if any(not h or h != h.strip() for h in header):
            raise InputError("Column names must be nonblank and have no surrounding spaces")
        for number, row in enumerate(reader, 2):
            if row and len(row) != len(header):
                raise InputError([{"row": number, "message": "CSV field count differs from header"}])
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
    if max(s.departure_time for s in sessions) - min(s.arrival_time for s in sessions) > timedelta(hours=72):
        raise InputError("Upload supports a horizon of at most 72 hours")
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


def check_scenario(sessions, station, prices, max_horizon_hours=72):
    """Validate the entire input before mutating a workspace or solving."""
    from ..utils.datetime_utils import floor_slot, ceil_slot
    if not sessions:
        raise InputError("Upload at least one charging session")
    if len({s.vehicle_id for s in sessions}) != len(sessions):
        raise InputError("Session IDs must be unique")
    start, end = min(s.arrival_time for s in sessions), max(s.departure_time for s in sessions)
    if end - start > timedelta(hours=max_horizon_hours):
        raise InputError(f"This run supports a horizon of at most {max_horizon_hours} hours")
    ports, bound = {c.charger_id: c for c in station.chargers}, [s for s in sessions if s.charger_id]
    for i, s in enumerate(bound):
        port = ports.get(s.charger_id)
        if not station.fixed_connections or not port or port.connector_type != s.connector_type:
            raise InputError(f"Unknown/incompatible fixed plug for {s.vehicle_id}")
        if any(t.charger_id == s.charger_id and t.arrival_time < s.departure_time and t.departure_time > s.arrival_time for t in bound[:i]):
            raise InputError(f"Overlapping physical plug assignments on {s.charger_id}")
    if any(p.timestamp.minute % 15 or p.timestamp.second or p.timestamp.microsecond for p in prices):
        raise InputError("Prices must start on UTC quarter-hour boundaries")
    price_map, cursor = {p.timestamp: p.price_eur_per_kwh for p in prices}, floor_slot(start, 15)
    while cursor < ceil_slot(end, 15):
        if cursor not in price_map:
            raise InputError(f"Missing price at {cursor.isoformat()}; upload matching prices")
        cursor += timedelta(minutes=15)
