"""Read-only capacity decisions and explicit, solver-checked counterfactuals."""

from datetime import timedelta

from ..models import Contract, Session
from pydantic import Field
from .analytics import metrics
from .scenario import Scenario
from .schedule_validator import validate_schedule
from .scheduler import SchedulingError, optimize


class RosterRule(Contract):
    vehicle_id: str = Field(min_length=1, max_length=80)
    departure_time: str | None = Field(default=None, max_length=40)
    energy_required_kwh: float | None = Field(default=None, ge=0, le=1000)
    source_quote: str = Field(min_length=1, max_length=500)


def fork(scenario, sessions=None, station=None):
    candidate = Scenario("analysis", sessions if sessions is not None else list(scenario.sessions),
                         station or scenario.station, list(scenario.prices), label=scenario.label,
                         max_horizon_days=scenario.max_horizon_days)
    candidate.now, candidate.history = scenario.now, list(scenario.history)
    candidate.events = dict(scenario.events)
    return candidate


def solve_checked(scenario, capacity=False, seconds=4, charger_budget=None):
    schedule = optimize(scenario, time_limit_seconds=seconds, capacity=capacity, charger_budget=charger_budget)
    validate_schedule(scenario, schedule, charger_budget=charger_budget)
    schedule.validated, schedule.metrics = True, metrics(scenario, schedule)
    return schedule


def propose_constraints(scenario, rules):
    ids = {s.vehicle_id for s in scenario.sessions}
    if len({r.vehicle_id for r in rules}) != len(rules) or any(r.vehicle_id not in ids for r in rules):
        raise ValueError("Rules need distinct, existing vehicle IDs")
    patches = {r.vehicle_id: {k: v for k, v in r.model_dump().items()
                             if k in {"departure_time", "energy_required_kwh"} and v is not None} for r in rules}
    if any(not patch for patch in patches.values()):
        raise ValueError("Each rule needs a deadline or an energy target")
    sessions = [Session.model_validate({**s.model_dump(), **patches.get(s.vehicle_id, {})}) for s in scenario.sessions]
    if any(s.departure_time <= scenario.now for s in sessions if s.vehicle_id in patches):
        raise ValueError("Proposed deadlines must be in the future")
    schedule = solve_checked(fork(scenario, sessions=sessions))
    return {"activated": False, "state_version": scenario.state_version, "proposed_rules": rules,
            "validated": True, "solver_status": schedule.solver_status, "metrics": schedule.metrics,
            "scope": "Typed preview only. Validation checks physics, not whether the source text was interpreted correctly."}


def capacity_frontier(scenario, counts):
    if scenario.history or scenario.now != scenario.start:
        raise ValueError("Reset before a whole-horizon capacity study; completed energy cannot be resized")
    chargers = scenario.station.chargers
    mandatory = {s.charger_id for s in scenario.sessions if s.charger_id is not None}
    rows = []
    for count in sorted(set(counts)):
        if not 1 <= count <= len(chargers):
            raise ValueError("Candidate count exceeds installed charger inventory")
        if count < len(mandatory):
            rows.append({"chargers": count, "connection_kw": None, "unserved_kwh": None,
                         "meets_all_departures": False, "minimum_proven": False, "infeasibility_proven": True,
                         "solver_status": "PHYSICAL_PLUG_BINDINGS", "validated": False})
            continue
        station = scenario.station.model_copy(update={"fixed_connections": True})
        candidate = fork(scenario, station=station)
        try:
            schedule = solve_checked(candidate, capacity=True, charger_budget=count)
        except SchedulingError as exc:
            rows.append({"chargers": count, "connection_kw": None, "unserved_kwh": None,
                         "meets_all_departures": False, "minimum_proven": False, "infeasibility_proven": False,
                         "solver_status": "UNRESOLVED", "validated": False, "error": str(exc)})
            continue
        ready = schedule.metrics["unserved_kwh"] <= 1e-5
        rows.append({"chargers": count, "connection_kw": schedule.metrics["peak_power_kw"],
                     "unserved_kwh": schedule.metrics["unserved_kwh"], "meets_all_departures": ready,
                     "minimum_proven": ready and schedule.shortfall_optimal and schedule.cost_optimal,
                     "infeasibility_proven": not ready and schedule.shortfall_optimal,
                     "charger_ids": sorted({a.charger_id for a in schedule.allocations} | mandatory),
                     "solver_status": schedule.solver_status, "validated": True})
    return {"state_version": scenario.state_version, "candidates": rows,
            "scope": "Observed roster, actual installed charger ratings/connectors/availability, fixed plugs and current upper connection limit. The solver selects a subset within each tested count. No capex quote or reliability guarantee."}


def counterfactuals(scenario, vehicle_id):
    if vehicle_id not in {s.vehicle_id for s in scenario.sessions}:
        raise ValueError("Unknown vehicle_id")
    original = solve_checked(fork(scenario))
    rows = []
    for name in ("departure_plus_20_minutes", "connection_plus_11_kw"):
        try:
            station, sessions = scenario.station, list(scenario.sessions)
            if name.startswith("departure"):
                sessions = [Session.model_validate({**s.model_dump(), "departure_time": s.departure_time + timedelta(minutes=20)})
                            if s.vehicle_id == vehicle_id else s for s in sessions]
            else:
                station = type(station).model_validate({**station.model_dump(), "station_power_limit_kw": station.station_power_limit_kw + 11})
            result = solve_checked(fork(scenario, sessions=sessions, station=station))
            rows.append({"change": name, "validated": True, "solver_status": result.solver_status,
                         "unserved_kwh": result.metrics["unserved_kwh"],
                         "improvement_kwh": original.metrics["unserved_kwh"] - result.metrics["unserved_kwh"],
                         "vehicle": next(v for v in result.metrics["vehicles"] if v["vehicle_id"] == vehicle_id)})
        except (ValueError, SchedulingError) as exc:
            rows.append({"change": name, "validated": False, "error": str(exc)})
    return {"activated": False, "state_version": scenario.state_version, "vehicle_id": vehicle_id,
            "experiments": rows, "method": "Controlled re-solves, not MIP duals or a minimal infeasible subsystem."}
