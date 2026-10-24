"""Bounded CSV ingestion and scenario checks; errors retain row/column context."""

import csv
from datetime import datetime, timedelta, timezone
import io
import math

import pandas as pd
from pydantic import ValidationError

from ..models import Price, Session, Station

MAX_UPLOAD = 2 * 1024 * 1024
REQUIRED = {"vehicle_id", "arrival_time", "departure_time", "energy_required_kwh", "max_charging_power_kw"}


class InputError(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [{"message": str(errors)}]
        super().__init__(self.errors[0]["message"])


def csv_frame(content: bytes) -> pd.DataFrame:
    if len(content) > MAX_UPLOAD:
        raise InputError("CSV exceeds the 2 MiB limit")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text), strict=True)
        header = next(reader, [])
        if len(header) != len(set(header)):
            raise InputError("Duplicate CSV columns")
        if any(not name or name != name.strip() for name in header):
            raise InputError("CSV column names must be nonempty and have no surrounding whitespace")
        for number, row in enumerate(reader, 2):
            if row and len(row) != len(header):
                raise InputError([{"row": number, "message": "CSV row has a different number of fields than the header"}])
        return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, on_bad_lines="error")
    except (UnicodeDecodeError, csv.Error, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InputError("Expected a nonempty UTF-8 CSV with consistent columns") from exc


def parse_sessions(content: bytes) -> list[Session]:
    frame = csv_frame(content)
    missing = REQUIRED - set(frame.columns)
    unknown = set(frame.columns) - REQUIRED - {"connector_type"}
    if missing or unknown:
        raise InputError(f"Missing columns: {', '.join(sorted(missing)) or 'none'}; unsupported columns: {', '.join(sorted(unknown)) or 'none'}")
    if not 1 <= len(frame) <= 100:
        raise InputError("Upload must contain between 1 and 100 sessions")
    errors, sessions, seen = [], [], set()
    for number, row in enumerate(frame.to_dict("records"), 2):
        try:
            session = Session.model_validate(row)
            if session.vehicle_id in seen:
                errors.append({"row": number, "column": "vehicle_id", "message": "Duplicate vehicle_id"})
            seen.add(session.vehicle_id)
            sessions.append(session)
        except ValidationError as exc:
            errors.extend({"row": number, "column": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors())
    if errors:
        raise InputError(errors[:100])
    return sessions


def parse_prices(content: bytes) -> list[Price]:
    frame = csv_frame(content)
    if set(frame.columns) != {"timestamp", "price_eur_per_kwh"} or not 1 <= len(frame) <= 1000:
        raise InputError("Price CSV requires timestamp,price_eur_per_kwh and at most 1000 rows")
    prices = []
    for number, row in enumerate(frame.to_dict("records"), 2):
        try:
            prices.append(Price.model_validate(row))
        except ValidationError as exc:
            raise InputError([{"row": number, "message": e["msg"]} for e in exc.errors()]) from exc
    if len({p.timestamp for p in prices}) != len(prices):
        raise InputError("Duplicate price timestamp")
    return sorted(prices, key=lambda p: p.timestamp)


def horizon(sessions, minutes):
    step = minutes * 60
    start = datetime.fromtimestamp(math.floor(min(s.arrival_time for s in sessions).timestamp() / step) * step, timezone.utc)
    end = datetime.fromtimestamp(math.ceil(max(s.departure_time for s in sessions).timestamp() / step) * step, timezone.utc)
    return start, end


def check_scenario(sessions: list[Session], station: Station, prices: list[Price]):
    start, end = horizon(sessions, station.slot_minutes)
    if end - start > timedelta(days=3):
        raise InputError("The demo supports a horizon of at most 72 hours")
    # Source price intervals are always 15 minutes, independent of scheduling slot duration.
    price_map = {p.timestamp: p.price_eur_per_kwh for p in prices}
    cursor = start
    while cursor < end:
        if cursor not in price_map:
            raise InputError(f"Missing 15-minute price at {cursor.isoformat()}; upload a matching price CSV")
        cursor += timedelta(minutes=15)
    if any(p.timestamp.minute % 15 or p.timestamp.second or p.timestamp.microsecond for p in prices):
        raise InputError("Prices must start on UTC quarter-hour boundaries")
    return start, end


def analytics(sessions, station, start, end):
    frame = pd.DataFrame([s.model_dump() for s in sessions])
    warnings = []
    for session in sessions:
        compatible = [c.max_power_kw for c in station.chargers if c.available and c.connector_type == session.connector_type]
        rate = min(session.max_charging_power_kw, max(compatible, default=0), station.station_power_limit_kw)
        available = (session.departure_time - session.arrival_time).total_seconds() / 3600
        lower_bound = max(0, session.energy_required_kwh - rate * available * station.charging_efficiency)
        if lower_bound > 1e-5:
            warnings.append({"vehicle_id": session.vehicle_id, "minimum_shortfall_kwh": lower_bound,
                             "reason": "No compatible available charger" if not compatible else "Energy target exceeds individual charging window"})
    return {"vehicles": len(frame), "sessions": len(frame), "total_energy_required_kwh": float(frame.energy_required_kwh.sum()),
            "available_chargers": sum(c.available for c in station.chargers), "horizon_start": start, "horizon_end": end,
            "horizon_hours": (end - start).total_seconds() / 3600, "warnings": warnings}
