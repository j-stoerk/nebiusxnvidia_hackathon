"""In-memory workspace orchestrating upload, optimize, simulation, and capacity."""

from ..config import ROOT, get_settings
from ..models import DemandTariff, PricePoint, ScheduleResult, SimulationEvent, StationConfig, VehicleSession
from .analytics_service import compute_analytics
from .baseline_scheduler import build_baseline
from .capacity_service import run_capacity_study
from .csv_validator import validate_prices_csv, validate_sessions_csv
from .optimizer import optimize_schedule
from .simulation_service import active_outages, apply_event, price_adjustments


class AppState:
    """Single in-memory MVP state (no database)."""

    def __init__(self):
        settings = get_settings()
        self.sessions: list[VehicleSession] = []
        self.prices: list[PricePoint] = []
        self.station = StationConfig(
            station_power_limit_kw=settings.default_station_power_kw,
            charger_count=settings.default_charger_count,
            charger_max_power_kw=settings.default_charger_power_kw,
            slot_minutes=settings.default_slot_minutes,
            charging_efficiency=1.0,
            fixed_connections=True,
            demand_tariff=DemandTariff(eur_per_kw=15.2, prior_peak_kw=40.0),
        )
        self.events: list[SimulationEvent] = []
        self.baseline: ScheduleResult | None = None
        self.optimized: ScheduleResult | None = None
        self.capacity_study: dict | None = None
        self.stale = False
        self.last_error: str | None = None

    def snapshot(self) -> dict:
        comparison = None
        if self.baseline and self.optimized:
            bm, om = self.baseline.metrics, self.optimized.metrics
            comparison = {
                "baseline_cost_eur": bm.cost_eur,
                "optimized_cost_eur": om.cost_eur,
                "cost_savings_eur": round(bm.cost_eur - om.cost_eur, 4),
                "baseline_energy_cost_eur": bm.energy_cost_eur,
                "optimized_energy_cost_eur": om.energy_cost_eur,
                "baseline_demand_cost_eur": bm.demand_cost_eur,
                "optimized_demand_cost_eur": om.demand_cost_eur,
                "energy_cost_savings_eur": round(bm.energy_cost_eur - om.energy_cost_eur, 4),
                "demand_cost_savings_eur": round(bm.demand_cost_eur - om.demand_cost_eur, 4),
                "baseline_unserved_kwh": bm.unserved_kwh,
                "optimized_unserved_kwh": om.unserved_kwh,
                "baseline_peak_kw": bm.peak_power_kw,
                "optimized_peak_kw": om.peak_power_kw,
                "peak_reduction_kw": round(bm.peak_power_kw - om.peak_power_kw, 4),
                "prior_peak_kw": om.prior_peak_kw,
                "demand_tariff_eur_per_kw": om.demand_tariff_eur_per_kw,
                "charging_efficiency": om.charging_efficiency,
                "fixed_connections": self.station.fixed_connections,
            }
        at_risk = []
        active = self.optimized or self.baseline
        if active:
            at_risk = [v for v in active.metrics.vehicles if not v.target_met]

        return {
            "simulated": True,
            "station": self.station.model_dump(mode="json"),
            "sessions": [s.model_dump(mode="json") for s in self.sessions],
            "prices": [p.model_dump(mode="json") for p in self.prices],
            "events": [e.model_dump(mode="json") for e in self.events],
            "analytics": compute_analytics(self.sessions, self.station, self.prices),
            "baseline": self.baseline.model_dump(mode="json") if self.baseline else None,
            "optimized": self.optimized.model_dump(mode="json") if self.optimized else None,
            "comparison": comparison,
            "capacity_study": self.capacity_study,
            "at_risk": [v.model_dump(mode="json") for v in at_risk],
            "stale": self.stale,
            "last_error": self.last_error,
        }


STATE = AppState()


def load_demo_if_empty() -> None:
    """Load sample CSV + synthetic prices when the workspace is empty."""
    if STATE.sessions:
        return
    sample = ROOT / "data" / "sample_charging_sessions.csv"
    prices = ROOT / "data" / "synthetic_prices_15min.csv"
    if sample.is_file():
        STATE.sessions = validate_sessions_csv(sample.read_bytes())
    if prices.is_file():
        STATE.prices = validate_prices_csv(prices.read_bytes())
    else:
        STATE.prices = _default_prices(STATE.sessions)


def _default_prices(sessions: list[VehicleSession]) -> list[PricePoint]:
    from datetime import timedelta
    from ..utils.datetime_utils import floor_slot

    if not sessions:
        return []
    start = floor_slot(min(s.arrival_time for s in sessions), 15)
    end = max(s.departure_time for s in sessions)
    points = []
    cursor = start
    while cursor <= end:
        hour = cursor.hour
        rate = 0.12 if hour < 6 or hour >= 22 else (0.28 if 7 <= hour < 10 or 17 <= hour < 21 else 0.18)
        points.append(PricePoint(timestamp=cursor, price_eur_per_kwh=rate))
        cursor += timedelta(minutes=15)
    return points


def upload_sessions(session_bytes: bytes, price_bytes: bytes | None = None) -> dict:
    sessions = validate_sessions_csv(session_bytes)
    prices = validate_prices_csv(price_bytes) if price_bytes else STATE.prices
    if not prices:
        prices = _default_prices(sessions)
    STATE.sessions = sessions
    STATE.prices = prices
    STATE.events = []
    STATE.baseline = None
    STATE.optimized = None
    STATE.capacity_study = None
    STATE.stale = False
    STATE.last_error = None
    return STATE.snapshot()


def update_station(payload: dict) -> dict:
    data = {**payload}
    data.pop("chargers", None)
    station = StationConfig.model_validate(data)
    STATE.station = station
    STATE.stale = True
    STATE.capacity_study = None
    return STATE.snapshot()


def run_optimization() -> dict:
    if not STATE.sessions:
        raise ValueError("Upload charging sessions before optimizing")
    outages = active_outages(STATE.events)
    adjustments = price_adjustments(STATE.events)
    try:
        STATE.baseline = build_baseline(
            STATE.sessions, STATE.station, STATE.prices, outages, adjustments
        )
        STATE.optimized = optimize_schedule(
            STATE.sessions, STATE.station, STATE.prices, outages, adjustments
        )
        STATE.stale = False
        STATE.last_error = None
    except Exception as exc:
        STATE.last_error = str(exc)
        STATE.stale = True
        raise
    return STATE.snapshot()


def run_capacity(counts: list[int] | None = None) -> dict:
    STATE.capacity_study = run_capacity_study(STATE, counts=counts)
    return {**STATE.snapshot(), "capacity_study": STATE.capacity_study}


def simulate(event: SimulationEvent, reoptimize: bool = True) -> dict:
    result = apply_event(STATE.station, STATE.events, event)
    STATE.stale = True
    if reoptimize and STATE.sessions and result.get("applied"):
        run_optimization()
    return {"event_result": result, **STATE.snapshot()}


def reset_state() -> dict:
    global STATE
    STATE = AppState()
    load_demo_if_empty()
    return STATE.snapshot()
