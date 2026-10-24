from datetime import timedelta

import pytest
from pydantic import ValidationError

from backend.app.models import Allocation, Charger, DemandTariff, Session
from backend.app.services.analytics import metrics
from backend.app.services.planning import RosterRule, capacity_frontier, counterfactuals, propose_constraints
from backend.app.services.schedule_service import Workspaces, replan, snapshot
from backend.app.services.schedule_validator import InvalidSchedule, validate_schedule
from backend.app.services.scheduler import SchedulingError, baseline, optimize


def test_edf_and_llf_prioritize_urgent_arrival(small_scenario):
    s = small_scenario
    s.sessions[0].energy_required_kwh = 1.25
    s.sessions.append(Session(vehicle_id="urgent", arrival_time=s.start + timedelta(minutes=15),
                              departure_time=s.start + timedelta(minutes=45), energy_required_kwh=.75,
                              max_charging_power_kw=2))
    for policy in ("FCFS", "EDF", "LLF"):
        result = baseline(s, policy)
        validate_schedule(s, result)
        urgent = next(v for v in metrics(s, result)["vehicles"] if v["vehicle_id"] == "urgent")
        assert urgent["target_met"] == (policy != "FCFS")
    assert replan(s)
    assert set(snapshot(s)["references"]) == {"EDF", "LLF"}


def test_llf_uses_remaining_work_not_just_departure(small_scenario):
    s = small_scenario
    s.sessions[0].energy_required_kwh = 1.5
    s.sessions.append(Session(vehicle_id="small", arrival_time=s.start, departure_time=s.start + timedelta(minutes=30),
                              energy_required_kwh=.1, max_charging_power_kw=2))
    assert baseline(s, "EDF").allocations[0].vehicle_id == "small"
    assert baseline(s, "LLF").allocations[0].vehicle_id == "EV-1"


def test_terminal_taper_envelope_and_independent_rejection(small_scenario):
    s = small_scenario
    s.sessions = [Session.model_validate({**s.sessions[0].model_dump(), "energy_required_kwh": .9,
                                         "battery_capacity_kwh": 10, "initial_soc": .9})]
    for result in [baseline(s, name) for name in ("FCFS", "EDF", "LLF")] + [optimize(s)]:
        validate_schedule(s, result)
        assert metrics(s, result)["delivered_kwh"] == pytest.approx(.5904, abs=1e-6)
    bad = baseline(s)
    bad.allocations = [Allocation(vehicle_id="EV-1", charger_id="C1", start_time=s.start,
                                  end_time=s.start + timedelta(minutes=15), power_kw=2)]
    with pytest.raises(InvalidSchedule, match="taper"):
        validate_schedule(s, bad)
    with pytest.raises(ValidationError, match="headroom"):
        Session.model_validate({**s.sessions[0].model_dump(), "energy_required_kwh": 2})


def test_metered_demand_changes_optimum_and_respects_prior_peak(small_scenario):
    s = small_scenario
    s.station.demand_tariff = DemandTariff(eur_per_kw=10)
    result = optimize(s)
    validate_schedule(s, result)
    measured = metrics(s, result)
    assert measured["peak_power_kw"] == pytest.approx(1, abs=1e-5)
    assert measured["cost_eur"] == pytest.approx(10.55, abs=1e-5)
    s.station.demand_tariff.prior_peaks_kw = {s.start.strftime("%Y-%m"): 2}
    measured = metrics(s, optimize(s))
    assert measured["demand_cost_eur"] == 0
    assert measured["energy_cost_eur"] == pytest.approx(.1, abs=1e-5)


def test_demand_uses_average_not_instantaneous_peak(small_scenario):
    s = small_scenario
    s.station.demand_tariff = DemandTariff(eur_per_kw=10)
    result = baseline(s)
    result.allocations = [Allocation(vehicle_id="EV-1", charger_id="C1", start_time=s.start,
                                     end_time=s.start + timedelta(minutes=7.5), power_kw=2)]
    measured = metrics(s, result)
    assert measured["peak_power_kw"] == 2
    assert measured["demand_cost_eur"] == pytest.approx(10)


def test_capacity_requires_fixed_plugs_not_free_vehicle_moves(small_scenario):
    s = small_scenario
    s.sessions[0].energy_required_kwh = .5
    s.sessions.append(Session.model_validate({**s.sessions[0].model_dump(), "vehicle_id": "EV-2"}))
    s.station.chargers.append(Charger(charger_id="C2", max_power_kw=2))
    report = capacity_frontier(s, [1, 2])
    one, two = report["candidates"]
    assert one["infeasibility_proven"] and not one["meets_all_departures"]
    assert two["minimum_proven"] and two["connection_kw"] == pytest.approx(1, abs=1e-5)
    assert not s.station.fixed_connections and len(s.station.chargers) == 2
    s.station.fixed_connections = True
    for policy in ("FCFS", "EDF", "LLF"):
        validate_schedule(s, baseline(s, policy))


def test_typed_roster_preview_and_counterfactual_do_not_activate(small_scenario):
    s = small_scenario
    assert replan(s)
    old = s.optimized.model_dump()
    report = propose_constraints(s, [RosterRule(vehicle_id="EV-1", energy_required_kwh=1.5, source_quote="EV-1 needs 1.5 kWh")])
    assert report["validated"] and not report["activated"]
    assert report["metrics"]["delivered_kwh"] == pytest.approx(1.5, abs=1e-5)
    assert counterfactuals(s, "EV-1")["experiments"][1]["validated"]
    assert s.optimized.model_dump() == old and s.state_version == 1
    with pytest.raises(ValueError, match="existing"):
        propose_constraints(s, [RosterRule(vehicle_id="absent", energy_required_kwh=1, source_quote="unknown")])


def test_fixed_connection_replan_preserves_actual_history_binding(small_scenario):
    s = small_scenario
    s.station.fixed_connections = True
    s.station.chargers.append(Charger(charger_id="C2", max_power_kw=2))
    s.now = s.start + timedelta(minutes=30)
    s.history = [Allocation(vehicle_id="EV-1", charger_id="C2", start_time=s.start,
                            end_time=s.start + timedelta(minutes=15), power_kw=2)]
    result = optimize(s)
    validate_schedule(s, result)
    assert {r.charger_id for r in result.allocations} == {"C2"}
    for policy in ("FCFS", "EDF", "LLF"):
        validate_schedule(s, baseline(s, policy))


def test_capacity_timeout_is_unknown_not_infeasible(small_scenario, monkeypatch):
    def timeout(*args, **kwargs):
        raise SchedulingError("Time limit")
    monkeypatch.setattr("backend.app.services.planning.solve_checked", timeout)
    row = capacity_frontier(small_scenario, [1])["candidates"][0]
    assert row["connection_kw"] is None
    assert not row["validated"] and not row["infeasibility_proven"] and not row["minimum_proven"]


def test_capacity_demo_has_two_plug_eight_kw_certificate():
    s = Workspaces().create(capacity=True)
    assert replan(s) and s.optimized.validated
    rows = capacity_frontier(s, [1, 2])["candidates"]
    assert rows[0]["infeasibility_proven"]
    assert rows[1]["minimum_proven"] and rows[1]["connection_kw"] == pytest.approx(8, abs=1e-5)
    assert metrics(s, s.optimized)["unserved_kwh"] < 1e-5
    assert s.optimized.metrics["demand_cost_eur"] < s.baseline.metrics["demand_cost_eur"]


def test_actual_plug_binding_survives_outage_and_reserves_idle_plug(small_scenario):
    from backend.app.models import Event
    s = small_scenario
    s.station.fixed_connections = True
    s.station.chargers.append(Charger(charger_id="C2", max_power_kw=2))
    s.sessions[0].charger_id = "C2"
    for result in [baseline(s, p) for p in ("FCFS", "EDF", "LLF")] + [optimize(s)]:
        validate_schedule(s, result)
        assert {r.charger_id for r in result.allocations} == {"C2"}
    s.events["fault"] = Event(event_id="fault", type="CHARGER_FAILED", charger_id="C2", start_time=s.start, end_time=s.end)
    for result in [baseline(s, p) for p in ("FCFS", "EDF", "LLF")] + [optimize(s)]:
        validate_schedule(s, result)
        assert not result.allocations  # A spare plug does not move a physically connected vehicle.
    s.events = {}
    s.sessions[0].energy_required_kwh = 0
    s.sessions.append(Session(vehicle_id="waiting", arrival_time=s.start, departure_time=s.end,
                              energy_required_kwh=1, max_charging_power_kw=2))
    s.station.chargers[0].available = False
    result = optimize(s)
    validate_schedule(s, result)
    assert metrics(s, result)["unserved_kwh"] == pytest.approx(1)


def test_capacity_selects_real_mixed_hardware_and_ignores_offline_ports(small_scenario):
    s = small_scenario
    s.station.chargers[0].available = False
    s.station.chargers.extend([Charger(charger_id="FAST", max_power_kw=4),
                               Charger(charger_id="CCS", max_power_kw=50, connector_type="CCS")])
    first = capacity_frontier(s, [1])["candidates"][0]
    assert first["minimum_proven"] and first["charger_ids"] == ["FAST"]
    s.sessions.append(Session(vehicle_id="truck", arrival_time=s.start, departure_time=s.end,
                              energy_required_kwh=1, max_charging_power_kw=2, connector_type="CCS"))
    one, two = capacity_frontier(s, [1, 2])["candidates"]
    assert one["infeasibility_proven"] and not one["meets_all_departures"]
    assert two["minimum_proven"] and two["charger_ids"] == ["CCS", "FAST"]
    assert two["connection_kw"] == pytest.approx(2, abs=1e-5)
