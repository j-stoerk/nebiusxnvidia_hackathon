"""Search actual installed hardware; distinguish certificates from incomplete searches."""
from itertools import combinations, islice
import math
import time

from .optimizer import optimize_schedule, OptimizationError
from .simulation_service import active_outages, price_adjustments


def run_capacity_study(state, counts=None, power_limits=None):
    if not state.sessions:
        raise ValueError("Upload sessions before studying capacity")
    installed = sorted(state.station.chargers, key=lambda c: c.charger_id)
    total = len(installed)
    counts = sorted(set(counts or [*range(1, min(total, 10) + 1), total]))
    if any(not isinstance(n, int) or not 1 <= n <= total for n in counts):
        raise ValueError("Candidate counts must use installed chargers")
    if power_limits and any(limit > state.station.station_power_limit_kw or limit <= 0 for limit in power_limits):
        raise ValueError("Candidate limits cannot exceed the available site connection")
    bound = {s.charger_id for s in state.sessions if s.charger_id}
    mandatory = [c for c in installed if c.charger_id in bound]
    optional = [c for c in installed if c.charger_id not in bound]
    deadline = time.monotonic() + 12
    candidates = []
    for n in counts:
        if n < len(bound):
            candidates.append({"charger_count": n, "feasible": False, "proven": False,
                "outcome": "infeasible", "enumeration_complete": True,
                "reason": "Fewer ports than explicit physical plug bindings", "shortfall_optimal": True})
            continue
        subsets = ((*mandatory, *extra) for extra in combinations(optional, n - len(bound)))
        subset_count = math.comb(total - len(bound), n - len(bound))
        results, unresolved = [], False
        for ports in islice(subsets, 40):
            remaining = deadline - time.monotonic()
            if remaining <= .2:
                unresolved = True
                break
            try:
                result = optimize_schedule(state.sessions, state.station, state.prices,
                    active_outages(state.events), price_adjustments(state.events), time_limit_seconds=min(3, remaining),
                    charger_ids=[c.charger_id for c in ports],
                    power_limit_kw=min(power_limits) if power_limits else None, goal="peak")
                results.append(result)
                unresolved |= not result.shortfall_optimal or not result.peak_optimal
            except (OptimizationError, ValueError):
                unresolved = True
        complete = subset_count <= 40 and not unresolved
        served = [r for r in results if r.validated and r.metrics.unserved_kwh <= 1e-5]
        best = min(served, key=lambda r: (r.metrics.peak_power_kw, r.metrics.cost_eur)) if served else None
        if best:
            m = best.metrics
            candidates.append({"charger_count": n, "station_power_limit_kw": m.peak_power_kw,
                "peak_power_kw": m.peak_power_kw, "cost_eur": m.cost_eur, "energy_cost_eur": m.energy_cost_eur,
                "demand_cost_eur": m.demand_cost_eur, "unserved_kwh": m.unserved_kwh,
                "target_success_percent": m.target_success_percent, "feasible": True,
                "proven": best.validated, "validated": best.validated, "outcome": "feasible",
                "enumeration_complete": complete, "power_minimum_proven": complete and best.peak_optimal,
                "solver_status": best.solver_status, "runtime_seconds": best.runtime_seconds})
        else:
            candidates.append({"charger_count": n, "feasible": False, "proven": False,
                "outcome": "infeasible" if complete else "unresolved", "enumeration_complete": complete,
                "unserved_kwh": min((r.metrics.unserved_kwh for r in results), default=None),
                "reason": "Proven energy shortfall" if complete else "Search/solver limit; no infeasibility claim"})
    feasible = [c for c in candidates if c["feasible"]]
    recommendation = min(feasible, key=lambda c: (c["charger_count"], c["peak_power_kw"])) if feasible else None
    minimum_proven = bool(recommendation and recommendation.get("power_minimum_proven") and
        all(any(c["charger_count"] == n and c["outcome"] == "infeasible" for c in candidates)
            for n in range(1, recommendation["charger_count"])))
    return {"recommendation": recommendation, "candidates": candidates, "minimum_proven": minimum_proven,
        "simulated": True, "proof": {"method": "Physical-port MIP plus independent record validation",
        "fixed_connections": state.station.fixed_connections, "installed_chargers": total,
        "installed_power_limit_kw": state.station.station_power_limit_kw,
        "note": "Feasible means a checked schedule meets every target. A minimum additionally requires all smaller counts excluded and complete power optimization. Timeouts stay unresolved. This is a planning simulation, not a connection quote."}}
