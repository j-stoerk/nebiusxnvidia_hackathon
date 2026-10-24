"""Workspace isolation, version checks, transactional activation, and replanning."""

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import time
from uuid import uuid4

from .csv_validator import InputError, analytics, check_scenario, parse_prices, parse_sessions
from .analytics import metrics
from ..models import DemandTariff, Event, Session, Station
from .scenario import Scenario, available_at, freeze_history, price_at
from .schedule_validator import InvalidSchedule, validate_schedule
from .scheduler import SchedulingError, baseline, optimize

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "data" / "demo"


class Conflict(ValueError):
    pass


def expected(scenario, version):
    if version != scenario.state_version:
        raise Conflict(f"State changed: expected version {version}, current version {scenario.state_version}. Refresh and retry.")


def replan(scenario, optimized=True):
    began = time.perf_counter()
    try:
        candidate_base = baseline(scenario)
        validate_schedule(scenario, candidate_base)
        candidate_base.validated = True
        candidate_base.metrics = metrics(scenario, candidate_base)
        references = {name: baseline(scenario, name) for name in ("EDF", "LLF")}
        for reference in references.values():
            validate_schedule(scenario, reference)
            reference.validated = True
            reference.metrics = metrics(scenario, reference)
        candidate_opt = optimize(scenario) if optimized else None
        if candidate_opt is not None:
            validate_schedule(scenario, candidate_opt)
            candidate_opt.validated = True
            candidate_opt.metrics = metrics(scenario, candidate_opt)
        # Activate as a pair only after both schedules independently pass validation.
        scenario.schedule_version += 1
        scenario.baseline, scenario.optimized = candidate_base, candidate_opt
        scenario.references = references
        scenario.stale, scenario.last_error = False, None
        scenario.recovery_seconds = time.perf_counter() - began
        return True
    except (SchedulingError, InvalidSchedule) as exc:
        scenario.last_error = str(exc)
        # Existing schedules remain visible with their old versions; never activate a candidate.
        scenario.stale = scenario.baseline is None or scenario.baseline.state_version != scenario.state_version
        return False


class Workspaces:
    def __init__(self):
        self.items = OrderedDict()
        self.lock = threading.Lock()

    def create(self, stress=False, capacity=False):
        name = "infeasible_charging_sessions.csv" if stress else "sample_charging_sessions.csv"
        scenario = Scenario(str(uuid4()), parse_sessions((DEMO / name).read_bytes()),
                            Station.model_validate_json((DEMO / "station_config.json").read_text()),
                            parse_prices((DEMO / "synthetic_prices_15min.csv").read_bytes()),
                            label="Synthetic stress scenario" if stress else "Synthetic 50-vehicle demo")
        if capacity:
            scenario = _capacity_demo(scenario)
        else:
            # Retained legacy fixtures explicitly assume staff can move vehicles.
            scenario.station.fixed_connections = False
            scenario.label += " · vehicle moves assumed"
        replan(scenario, optimized=False)
        with self.lock:
            self.items[scenario.workspace_id] = (time.monotonic(), scenario)
            while len(self.items) > 16:
                self.items.popitem(last=False)
        return scenario

    def get(self, workspace_id):
        with self.lock:
            item = self.items.get(workspace_id)
            if item is None or time.monotonic() - item[0] > 4 * 3600:
                self.items.pop(workspace_id, None)
                raise KeyError("Workspace expired or does not exist; load a new demo")
            scenario = item[1]
            self.items[workspace_id] = (time.monotonic(), scenario)
            self.items.move_to_end(workspace_id)
            return scenario


def _capacity_demo(source):
    """Small two-shift fixture; published capacity rate used as an illustration."""
    start = datetime(2026, 10, 24, tzinfo=timezone.utc)
    offset = start - source.prices[0].timestamp
    sessions = [Session(vehicle_id=f"VAN-{i + 1:02}", arrival_time=start + timedelta(hours=arrival),
                        departure_time=start + timedelta(hours=arrival + 6), energy_required_kwh=energy,
                        max_charging_power_kw=11, battery_capacity_kwh=40, initial_soc=.25)
                for i, (arrival, energy) in enumerate([(6, 18), (6, 18), (14, 24), (14, 24)])]
    station = source.station.model_copy(update={"fixed_connections": True, "demand_tariff": DemandTariff(eur_per_kw=15.2)})
    prices = [p.model_copy(update={"timestamp": p.timestamp + offset}) for p in source.prices]
    return Scenario(source.workspace_id, sessions, station, prices, label="Synthetic two-shift depot · illustrative German demand price")


def apply_event(scenario, event: Event, version):
    existing = scenario.events.get(event.event_id)
    if existing is not None:
        if existing != event:
            raise Conflict("An event_id cannot be reused with different contents")
        # An exact retry is successful even if its original version is now old.
        return {"status": "duplicate_ignored", "event_id": event.event_id}
    expected(scenario, version)
    if len(scenario.events) >= 100:
        raise InputError("Reset the scenario after 100 simulation events")
    if event.charger_id and event.charger_id not in {c.charger_id for c in scenario.station.chargers}:
        raise InputError("Unknown charger_id")
    start = event.time if event.type == "CHARGER_RECOVERED" else event.start_time
    end = event.time if event.type == "CHARGER_RECOVERED" else event.end_time
    if start < scenario.now or end > scenario.end:
        raise InputError("Events must fall within the remaining simulation horizon; delivered history cannot change")
    scenario.events[event.event_id] = event
    scenario.state_version += 1
    scenario.stale = True
    success = replan(scenario)
    return {"status": "replanned" if success else "replan_failed", "event_id": event.event_id}


def advance(scenario, instant: datetime, version):
    expected(scenario, version)
    if not scenario.now < instant <= scenario.end:
        raise InputError("Simulation time must advance within the scenario horizon")
    try:
        history = freeze_history(scenario, instant)
    except ValueError as exc:
        raise Conflict(str(exc)) from exc
    scenario.history = history
    scenario.now = instant
    scenario.state_version += 1
    scenario.stale = True
    replan(scenario)


def update_station(scenario, station, version):
    expected(scenario, version)
    if station.fixed_connections and not scenario.station.fixed_connections and scenario.history:
        raise InputError("Restart the legacy scenario before switching to fixed plugs; current physical bindings are unknown")
    start, end = check_scenario(scenario.sessions, station, scenario.prices)
    # Retained events reference physical charger identities.
    ids = {c.charger_id for c in station.chargers}
    if any(e.charger_id and e.charger_id not in ids for e in scenario.events.values()):
        raise InputError("Cannot remove a charger referenced by an event; reset the scenario first")
    scenario.station = station
    scenario.start, scenario.end = start, end
    scenario.state_version += 1
    scenario.stale = True
    replan(scenario)


def upload(scenario, sessions_content, prices_content, version):
    expected(scenario, version)
    sessions = parse_sessions(sessions_content)
    prices = parse_prices(prices_content) if prices_content is not None else scenario.prices
    station = scenario.station.model_copy(update={"fixed_connections": True})
    start, end = check_scenario(sessions, station, prices)
    # All parsing and coverage checks precede replacing the existing simulation.
    scenario.sessions, scenario.prices = sessions, prices
    scenario.station = station
    scenario.start, scenario.end, scenario.now = start, end, start
    scenario.price_map = {p.timestamp: p.price_eur_per_kwh for p in prices}
    scenario.events, scenario.history = {}, []
    scenario.label = "Uploaded sessions · simulated station"
    scenario.state_version += 1
    scenario.stale = True
    replan(scenario)


def snapshot(scenario):
    comparison = None
    if scenario.baseline is not None and scenario.optimized is not None and not scenario.stale:
        b, o = scenario.baseline.metrics, scenario.optimized.metrics
        same_energy = abs(b["delivered_kwh"] - o["delivered_kwh"]) <= 1e-4
        comparison = {"baseline_cost_eur": b["cost_eur"], "optimized_cost_eur": o["cost_eur"],
                      "equal_delivered_energy": same_energy,
                      "cost_savings_eur": b["cost_eur"] - o["cost_eur"] if same_energy else None,
                      "cost_savings_percent": 100 * (b["cost_eur"] - o["cost_eur"]) / b["cost_eur"]
                      if same_energy and b["cost_eur"] > 1e-8 else None}
    return {"workspace_id": scenario.workspace_id, "label": scenario.label, "simulated": scenario.station.simulated,
            "state_version": scenario.state_version, "schedule_version": scenario.schedule_version,
            "now": scenario.now, "horizon_start": scenario.start, "horizon_end": scenario.end,
            "station": scenario.station, "sessions": scenario.sessions,
            "analytics": analytics(scenario.sessions, scenario.station, scenario.start, scenario.end),
            "baseline": scenario.baseline, "optimized": scenario.optimized, "comparison": comparison,
            "references": scenario.references,
            "stale": scenario.stale, "last_error": scenario.last_error, "recovery_seconds": scenario.recovery_seconds,
            "history_records": len(scenario.history), "events": list(scenario.events.values()),
            "charger_status": [{"charger_id": c.charger_id, "available_now": available_at(scenario, c, scenario.now)} for c in scenario.station.chargers]}
