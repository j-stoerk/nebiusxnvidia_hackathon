"""Apply simulated charger and price events to in-memory state."""

from ..models import SimulationEvent, StationConfig


def apply_event(station: StationConfig, events: list[SimulationEvent], event: SimulationEvent) -> dict:
    """
    Mutate station availability for permanent recoveries/settings-style failures,
    and record the event for scheduling overlays.
    Returns a small result summary. All events are labeled simulated.
    """
    existing = next((e for e in events if e.event_id == event.event_id), None)
    if existing:
        if existing != event:
            raise ValueError("Event ID already exists with different content")
        return {"applied": False, "reason": "duplicate_event_id", "event_id": event.event_id}

    if event.type == "CHARGER_FAILED":
        for charger in station.chargers:
            if charger.charger_id == event.charger_id:
                # Outage window is handled via event overlays; mark simulated status.
                charger.simulated = True
                break
        else:
            raise ValueError(f"Unknown charger_id: {event.charger_id}")

    if event.type == "CHARGER_RECOVERED":
        for charger in station.chargers:
            if charger.charger_id == event.charger_id:
                charger.simulated = True
                break
        else:
            raise ValueError(f"Unknown charger_id: {event.charger_id}")

    events.append(event)
    return {
        "applied": True,
        "event_id": event.event_id,
        "type": event.type,
        "simulated": True,
        "message": f"Simulated event {event.type} recorded",
    }


def active_outages(events: list[SimulationEvent]) -> list[tuple]:
    """Return (charger_id, start, end) windows for CHARGER_FAILED events."""
    outages = []
    for event in events:
        if event.type != "CHARGER_FAILED" or not event.charger_id:
            continue
        end = event.end_time
        recoveries = [e.time for e in events if e.type == "CHARGER_RECOVERED" and e.charger_id == event.charger_id
                      and e.time and event.start_time <= e.time < end]
        if recoveries:
            end = min(recoveries)
        outages.append((event.charger_id, event.start_time, end))
    return outages


def price_adjustments(events: list[SimulationEvent]) -> list[tuple]:
    """Return (start, end, add_eur_per_kwh) for PRICE_CHANGED events."""
    result = []
    for event in events:
        if event.type == "PRICE_CHANGED" and event.start_time and event.end_time:
            result.append((event.start_time, event.end_time, event.add_eur_per_kwh or 0.0))
    return result
