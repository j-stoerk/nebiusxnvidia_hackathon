"""Transactional per-browser simulations; validated plans and delivery history only."""
from collections import OrderedDict
from contextvars import ContextVar
from functools import wraps
import json
import threading
import time

from ..config import ROOT
from ..models import StationConfig
from .analytics_service import compute_analytics
from .baseline_scheduler import build_baseline
from .capacity_service import run_capacity_study
from .csv_validator import check_scenario, validate_prices_csv, validate_sessions_csv
from .optimizer import optimize_schedule
from .simulation_service import active_outages, apply_event, price_adjustments

WORKSPACE = ContextVar("chargewise_workspace", default="local")
CURRENT_STATE = ContextVar("active_simulation", default=None)
EXPECTED_VERSION = ContextVar("expected_version", default=None)
POOL, POOL_LOCK = OrderedDict(), threading.RLock()
DEMO = ROOT / "data/demo/prepared"


class Conflict(ValueError):
    pass


def _comparison(baseline, optimized, station):
    bm, om = baseline.metrics, optimized.metrics
    equal = abs(bm.unserved_kwh - om.unserved_kwh) <= 1e-5
    result = {f"{prefix}_{key}": getattr(m, key) for prefix, m in (("baseline", bm), ("optimized", om))
              for key in ("cost_eur", "energy_cost_eur", "demand_cost_eur", "unserved_kwh")}
    result.update(baseline_peak_kw=bm.peak_power_kw, optimized_peak_kw=om.peak_power_kw,
        cost_savings_eur=bm.cost_eur - om.cost_eur if equal else None,
        energy_cost_savings_eur=bm.energy_cost_eur - om.energy_cost_eur if equal else None,
        demand_cost_savings_eur=bm.demand_cost_eur - om.demand_cost_eur if equal else None,
        peak_reduction_kw=bm.peak_power_kw - om.peak_power_kw, equal_energy_comparison=equal,
        prior_peak_kw=station.demand_tariff.prior_peak_kw, demand_tariff_eur_per_kw=station.demand_tariff.eur_per_kw,
        charging_efficiency=station.charging_efficiency, fixed_connections=station.fixed_connections,
        optimization_goal=station.optimization_goal)
    return result


class AppState:
    def __init__(self):
        self.sessions, self.prices, self.events, self.history = [], [], [], []
        self.station = StationConfig.model_validate_json((DEMO / "station.json").read_text())
        self.baseline = self.optimized = self.capacity_study = None
        self.references, self.version, self.now = {}, 1, None
        self.stale, self.last_error = False, None
        self.lock = threading.RLock()

    def snapshot(self):
        with self.lock:
            active = self.optimized or self.baseline
            return {"simulated": True, "state_version": self.version, "now": self.now,
                "station": self.station.model_dump(mode="json"),
                "sessions": [s.model_dump(mode="json") for s in self.sessions],
                "prices": [p.model_dump(mode="json") for p in self.prices],
                "events": [e.model_dump(mode="json") for e in self.events],
                "analytics": compute_analytics(self.sessions, self.station, self.prices),
                "baseline": self.baseline.model_dump(mode="json") if self.baseline else None,
                "optimized": self.optimized.model_dump(mode="json") if self.optimized else None,
                "references": {k: v.model_dump(mode="json") for k, v in self.references.items()},
                "comparison": _comparison(self.baseline, self.optimized, self.station) if self.baseline and self.optimized else None,
                "capacity_study": self.capacity_study,
                "at_risk": [v.model_dump(mode="json") for v in active.metrics.vehicles if not v.target_met] if active else [],
                "stale": self.stale, "last_error": self.last_error}


def current_state():
    pinned = CURRENT_STATE.get()
    if pinned is not None:
        return pinned
    key, instant = WORKSPACE.get(), time.monotonic()
    with POOL_LOCK:
        item = POOL.pop(key, None)
        state = item[1] if item and instant - item[0] < 4 * 3600 else AppState()
        POOL[key] = (instant, state)
        while len(POOL) > 16:
            POOL.popitem(last=False)
        return state


class StateProxy:
    def __getattr__(self, name):
        return getattr(current_state(), name)

    def __setattr__(self, name, value):
        setattr(current_state(), name, value)


STATE = StateProxy()


def mutation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        state = current_state()
        with state.lock:
            expected = EXPECTED_VERSION.get()
            event = args[0] if function.__name__ == "simulate" and args else None
            retry = event is not None and any(e == event for e in state.events)
            if expected is not None and expected != state.version and not retry:
                raise Conflict("This workspace changed; refresh before retrying")
            EXPECTED_VERSION.set(None)
            return function(*args, **kwargs)
    return wrapped


def load_demo_if_empty():
    with STATE.lock:
        if not STATE.sessions:
            STATE.sessions = validate_sessions_csv((DEMO / "sessions.csv").read_bytes())
            STATE.prices = validate_prices_csv((DEMO / "prices.csv").read_bytes())
            STATE.now = min(s.arrival_time for s in STATE.sessions)


@mutation
def upload_sessions(session_bytes, price_bytes=None):
    sessions = validate_sessions_csv(session_bytes)
    prices = validate_prices_csv(price_bytes) if price_bytes else STATE.prices
    check_scenario(sessions, STATE.station, prices)
    STATE.sessions, STATE.prices, STATE.events, STATE.history = sessions, prices, [], []
    STATE.baseline = STATE.optimized = STATE.capacity_study = None
    STATE.references, STATE.stale, STATE.last_error = {}, False, None
    STATE.now = min(s.arrival_time for s in sessions)
    STATE.version += 1
    return STATE.snapshot()


@mutation
def update_station(payload):
    station = StationConfig.model_validate(payload)
    if STATE.sessions:
        check_scenario(STATE.sessions, station, STATE.prices)
    active = {r.charger_id for r in STATE.history if any(s.vehicle_id == r.vehicle_id and s.departure_time > STATE.now for s in STATE.sessions)}
    if active - {c.charger_id for c in station.chargers}:
        raise ValueError("Cannot remove a plug occupied by a vehicle with delivery history")
    STATE.station, STATE.stale, STATE.capacity_study = station, True, None
    STATE.version += 1
    return STATE.snapshot()


@mutation
def run_optimization(report=None):
    report = report or (lambda *_: None)
    outages, adjustments = active_outages(STATE.events), price_adjustments(STATE.events)
    args = (STATE.sessions, STATE.station, STATE.prices, outages, adjustments)
    try:
        check_scenario(STATE.sessions, STATE.station, STATE.prices)
        report("inputs", "complete")
        plans = {}
        for name in ("FCFS", "EDF", "LLF"):
            report(name, "running")
            plans[name] = build_baseline(*args, policy=name, history=STATE.history, now=STATE.now)
            report(name, "complete", plans[name].metrics.model_dump(mode="json"))
        optimized = optimize_schedule(*args, history=STATE.history, now=STATE.now, report=report)
    except Exception as exc:
        STATE.stale, STATE.last_error = True, str(exc)
        raise
    STATE.baseline, STATE.optimized = plans.pop("FCFS"), optimized
    STATE.references, STATE.stale, STATE.last_error = plans, False, None
    STATE.version += 1
    return STATE.snapshot()


@mutation
def replace_scenario(sessions, prices, station):
    """Validate the complete editor draft before replacing any live inputs."""
    if len(prices) != len({p.timestamp for p in prices}):
        raise ValueError("Price timestamps must be unique")
    prices = sorted(prices, key=lambda p: p.timestamp)
    check_scenario(sessions, station, prices)
    STATE.sessions, STATE.prices, STATE.station = sessions, prices, station
    STATE.events, STATE.history, STATE.references = [], [], {}
    STATE.baseline = STATE.optimized = STATE.capacity_study = None
    STATE.stale, STATE.last_error = False, None
    STATE.now = min(s.arrival_time for s in sessions)
    STATE.version += 1
    return STATE.snapshot()


@mutation
def run_capacity(counts=None):
    if STATE.history:
        raise ValueError("Reset the demo to study whole-roster capacity before delivery begins")
    STATE.capacity_study = run_capacity_study(current_state(), counts=counts)
    return STATE.snapshot()


@mutation
def simulate(event, reoptimize=True):
    existing = next((e for e in STATE.events if e.event_id == event.event_id), None)
    if existing:
        if existing != event:
            raise Conflict("Event ID already exists with different content")
        return {"event_result": {"applied": False, "reason": "duplicate_event_id", "event_id": event.event_id}, **STATE.snapshot()}
    start = event.time if event.type == "CHARGER_RECOVERED" else event.start_time
    end = event.time if event.type == "CHARGER_RECOVERED" else event.end_time
    if not STATE.sessions or start < STATE.now or end > max(s.departure_time for s in STATE.sessions):
        raise ValueError("Events must fit within the remaining scenario horizon")
    result = apply_event(STATE.station, STATE.events, event)
    STATE.stale = True
    STATE.capacity_study = None
    STATE.version += 1
    if reoptimize:
        run_optimization()
    return {"event_result": result, **STATE.snapshot()}


@mutation
def advance(moment):
    from ..models import Allocation
    active = STATE.optimized or STATE.baseline
    if STATE.stale or not active or not STATE.now <= moment <= max(s.departure_time for s in STATE.sessions):
        raise ValueError("Advance needs a current validated plan and a time inside the remaining horizon")
    STATE.history = [Allocation(**{**r.model_dump(), "end_time": min(r.end_time, moment)}) for r in active.allocations if r.start_time < moment]
    STATE.now = moment
    STATE.capacity_study = None
    STATE.version += 1
    return run_optimization()


@mutation
def reset_state():
    fresh = AppState()
    fresh.version = STATE.version + 1
    with POOL_LOCK:
        POOL[WORKSPACE.get()] = (time.monotonic(), fresh)
    if CURRENT_STATE.get() is not None:
        CURRENT_STATE.set(fresh)
    load_demo_if_empty()
    return STATE.snapshot()
