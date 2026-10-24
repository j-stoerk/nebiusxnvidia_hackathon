"""Capacity planning: find smallest charger count / site power that still meets targets."""

from copy import deepcopy

from ..models import StationConfig
from .optimizer import OptimizationError, optimize_schedule
from .simulation_service import active_outages, price_adjustments


def run_capacity_study(state, counts: list[int] | None = None, power_limits: list[float] | None = None) -> dict:
    """
    Independently re-solve with subsets of installed chargers and optional lower power caps.
    A candidate is 'proven' only when unserved energy is ~0 and the solver finishes.
    """
    if not state.sessions:
        raise ValueError("Upload sessions before running a capacity study")

    counts = counts or [2, 4, 6, 8, 10, len(state.station.chargers)]
    counts = sorted({max(1, min(c, len(state.station.chargers))) for c in counts})
    power_limits = power_limits or [
        max(11.0, round(state.station.station_power_limit_kw * f, 1))
        for f in (0.25, 0.4, 0.55, 0.7, 0.85, 1.0)
    ]
    power_limits = sorted(set(power_limits))

    outages = active_outages(state.events)
    adjustments = price_adjustments(state.events)
    installed = sorted(state.station.chargers, key=lambda c: c.charger_id)

    candidates = []
    for n in counts:
        subset = installed[:n]
        ids = [c.charger_id for c in subset]
        for limit in power_limits:
            try:
                result = optimize_schedule(
                    state.sessions,
                    state.station,
                    state.prices,
                    outages,
                    adjustments,
                    time_limit_seconds=4.0,
                    charger_ids=ids,
                    power_limit_kw=limit,
                )
                ok = result.metrics.unserved_kwh <= 1e-3
                candidates.append(
                    {
                        "charger_count": n,
                        "station_power_limit_kw": limit,
                        "feasible": ok,
                        "proven": ok and "OPTIMAL" in result.solver_status,
                        "unserved_kwh": result.metrics.unserved_kwh,
                        "peak_power_kw": result.metrics.peak_power_kw,
                        "cost_eur": result.metrics.cost_eur,
                        "energy_cost_eur": result.metrics.energy_cost_eur,
                        "demand_cost_eur": result.metrics.demand_cost_eur,
                        "target_success_percent": result.metrics.target_success_percent,
                        "solver_status": result.solver_status,
                        "runtime_seconds": result.runtime_seconds,
                    }
                )
            except OptimizationError as exc:
                candidates.append(
                    {
                        "charger_count": n,
                        "station_power_limit_kw": limit,
                        "feasible": False,
                        "proven": False,
                        "unserved_kwh": None,
                        "peak_power_kw": None,
                        "cost_eur": None,
                        "error": str(exc),
                    }
                )

    feasible = [c for c in candidates if c.get("feasible")]
    feasible.sort(key=lambda c: (c["charger_count"], c["station_power_limit_kw"], c["cost_eur"] or 1e9))
    recommendation = feasible[0] if feasible else None

    proof = {
        "method": "Independent OR-Tools re-solves on charger subsets and power caps",
        "fixed_connections": state.station.fixed_connections,
        "charging_efficiency": state.station.charging_efficiency,
        "demand_tariff_eur_per_kw": state.station.demand_tariff.eur_per_kw,
        "prior_peak_kw": state.station.demand_tariff.prior_peak_kw,
        "installed_chargers": len(state.station.chargers),
        "installed_power_limit_kw": state.station.station_power_limit_kw,
        "note": (
            "Proven means all energy targets met under the candidate hardware with an optimal/feasible solve. "
            "This is a planning simulation, not a utility interconnection quote."
        ),
    }

    return {
        "recommendation": recommendation,
        "candidates": candidates,
        "proof": proof,
        "simulated": True,
    }
