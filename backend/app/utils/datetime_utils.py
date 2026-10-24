"""UTC timestamp helpers for the 15-minute charging grid."""

from datetime import datetime, timedelta, timezone


def ensure_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must include a timezone (Z or an explicit offset)")
    return value.astimezone(timezone.utc)


def hours(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 3600.0)


def floor_slot(moment: datetime, slot_minutes: int) -> datetime:
    step = slot_minutes * 60
    epoch = int(moment.timestamp())
    return datetime.fromtimestamp((epoch // step) * step, timezone.utc)


def ceil_slot(moment: datetime, slot_minutes: int) -> datetime:
    step = slot_minutes * 60
    epoch = int(moment.timestamp())
    rounded = ((epoch + step - 1) // step) * step
    return datetime.fromtimestamp(rounded, timezone.utc)


def iter_slots(start: datetime, end: datetime, slot_minutes: int):
    cursor = floor_slot(start, slot_minutes)
    step = timedelta(minutes=slot_minutes)
    while cursor < end:
        nxt = cursor + step
        yield cursor, nxt
        cursor = nxt
