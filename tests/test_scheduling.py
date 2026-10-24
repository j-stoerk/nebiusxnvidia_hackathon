from datetime import timedelta
import math

import pytest

from backend.app.services.analytics import metrics
from backend.app.models import Allocation, Charger, Event, Session
from backend.app.services.scenario import battery_energy
from backend.app.services.schedule_validator import InvalidSchedule, validate_schedule
from backend.app.services.scheduler import baseline, optimize
from backend.app.services.schedule_service import Conflict, Workspaces, advance, apply_event, replan, snapshot


def test_exact_cost_and_energy_priority(small_scenario):
    s = small_scenario
    b, o = baseline(s), optimize(s)
    assert validate_schedule(s, b) and validate_schedule(s, o)
    assert metrics(s, b)["cost_eur"] == pytest.approx(1)
    assert metrics(s, o)["cost_eur"] == pytest.approx(.1, abs=1e-6)
    assert metrics(s, o)["unserved_kwh"] < 1e-5
    assert o.shortfall_optimal and o.cost_optimal


def test_negative_price_does_not_overcharge(small_scenario):
    s = small_scenario
    for p in s.prices:
        p.price_eur_per_kwh = -1
    s.price_map = {p.timestamp: p.price_eur_per_kwh for p in s.prices}
    o = optimize(s)
    validate_schedule(s, o)
    assert metrics(s, o)["delivered_kwh"] == pytest.approx(1, abs=1e-6)
    assert metrics(s, o)["cost_eur"] == pytest.approx(-1, abs=1e-6)


def test_zero_energy_and_administratively_disabled_charger(small_scenario):
    s = small_scenario
    s.sessions[0].energy_required_kwh = 0
    o = optimize(s)
    validate_schedule(s, o)
    assert not o.allocations and metrics(s, o)["target_success_percent"] == 100
    s.sessions[0].energy_required_kwh = 1
    s.station.chargers[0].available = False
    apply_event(s, Event(event_id="recovery", type="CHARGER_RECOVERED", charger_id="C1", time=s.start), 1)
    assert s.optimized.metrics["unserved_kwh"] == pytest.approx(1)


def test_individual_shortfall_and_efficiency(small_scenario):
    s = small_scenario
    s.station.charging_efficiency = .8
    s.sessions[0].energy_required_kwh = 10
    o = optimize(s)
    validate_schedule(s, o)
    assert metrics(s, o)["unserved_kwh"] == pytest.approx(8.4, abs=1e-5)


def test_heterogeneous_compatibility_and_capacity(small_scenario):
    s = small_scenario
    s.station.chargers.append(Charger(charger_id="CCS", max_power_kw=5, connector_type="CCS"))
    s.sessions.append(Session(vehicle_id="EV-2", arrival_time=s.start, departure_time=s.end,
                              energy_required_kwh=2, max_charging_power_kw=4, connector_type="CCS"))
    o = optimize(s)
    validate_schedule(s, o)
    assert metrics(s, o)["unserved_kwh"] == pytest.approx(1, abs=1e-5)
    assert all(a.charger_id == "CCS" for a in o.allocations if a.vehicle_id == "EV-2")
    assert metrics(s, o)["peak_power_kw"] <= 2 + 1e-5


def test_partial_windows_are_respected(small_scenario):
    s = small_scenario
    s.sessions[0].arrival_time += timedelta(minutes=7)
    s.sessions[0].departure_time -= timedelta(minutes=8)
    o = optimize(s)
    validate_schedule(s, o)
    assert metrics(s, o)["unserved_kwh"] < 1e-5


def test_validator_rejects_station_cap_connector_collision_and_duplicate_reference(small_scenario):
    s = small_scenario
    record = Allocation(vehicle_id="EV-1", charger_id="C1", start_time=s.start,
                        end_time=s.start + timedelta(minutes=15), power_kw=2)
    b = baseline(s)
    b.allocations = [record, record]  # Same object identity must still be detected twice.
    with pytest.raises(InvalidSchedule, match="Station cap|multiple"):
        validate_schedule(s, b)


@pytest.mark.parametrize("mutation,match", [
    ({"power_kw": 3}, "Power rating|Station cap"),
    ({"charger_id": "unknown"}, "Unknown charger"),
    ({"vehicle_id": "unknown"}, "Unknown vehicle"),
])
def test_validator_rejects_corruption(small_scenario, mutation, match):
    s = small_scenario
    b = baseline(s)
    b.allocations[0] = b.allocations[0].model_copy(update=mutation)
    with pytest.raises(InvalidSchedule, match=match):
        validate_schedule(s, b)


def test_validator_catches_outage_inside_a_long_record(small_scenario):
    s = small_scenario
    s.events["out"] = Event(event_id="out", type="CHARGER_FAILED", charger_id="C1",
                            start_time=s.start + timedelta(minutes=10), end_time=s.start + timedelta(minutes=20))
    b = baseline(s)
    b.allocations = [Allocation(vehicle_id="EV-1", charger_id="C1", start_time=s.start, end_time=s.end, power_kw=1)]
    with pytest.raises(InvalidSchedule, match="unavailable"):
        validate_schedule(s, b)


def test_replay_is_idempotent_and_reused_id_conflicts(small_scenario):
    s = small_scenario
    event = Event(event_id="price", type="PRICE_CHANGED", start_time=s.start,
                  end_time=s.end, add_eur_per_kwh=.5)
    assert apply_event(s, event, 1)["status"] == "replanned"
    assert apply_event(s, event, 1)["status"] == "duplicate_ignored"
    assert s.state_version == 2
    with pytest.raises(Conflict):
        apply_event(s, event.model_copy(update={"add_eur_per_kwh": .2}), 2)


def test_history_survives_outage_and_price_replanning(small_scenario):
    s = small_scenario
    assert replan(s)
    advance(s, s.start + timedelta(minutes=45), 1)
    history = [a.model_dump() for a in s.history]
    delivered = sum(battery_energy(a) for a in s.history)
    assert delivered > 0
    apply_event(s, Event(event_id="fail", type="CHARGER_FAILED", charger_id="C1",
                         start_time=s.now, end_time=s.end), 2)
    assert history == [a.model_dump() for a in s.history]
    assert sum(battery_energy(a) for a in s.optimized.allocations) == pytest.approx(delivered)
    assert [a.model_dump() for a in s.baseline.allocations if a.end_time <= s.now] == history
    with pytest.raises(ValueError, match="history"):
        apply_event(s, Event(event_id="past", type="PRICE_CHANGED", start_time=s.start, end_time=s.end,
                             add_eur_per_kwh=1), s.state_version)


def test_recovery_and_zero_remaining_horizon(small_scenario):
    s = small_scenario
    apply_event(s, Event(event_id="fail", type="CHARGER_FAILED", charger_id="C1", start_time=s.start, end_time=s.end), 1)
    assert s.optimized.metrics["delivered_kwh"] == 0
    apply_event(s, Event(event_id="recover", type="CHARGER_RECOVERED", charger_id="C1", time=s.start + timedelta(minutes=30)), 2)
    assert s.optimized.metrics["unserved_kwh"] < 1e-5
    advance(s, s.end, s.state_version)
    validate_schedule(s, s.optimized)
    assert s.optimized.metrics["unserved_kwh"] < 1e-5


def test_failed_replan_never_activates_invalid_candidate(small_scenario, monkeypatch):
    s = small_scenario
    assert replan(s)
    original = s.optimized.model_dump()
    def invalid(scenario):
        result = baseline(scenario)
        result.allocations[0] = result.allocations[0].model_copy(update={"power_kw": 1000})
        return result
    monkeypatch.setattr("backend.app.services.schedule_service.optimize", invalid)
    apply_event(s, Event(event_id="price", type="PRICE_CHANGED", start_time=s.start, end_time=s.end, add_eur_per_kwh=.2), 1)
    assert s.stale and s.last_error
    assert s.optimized.model_dump() == original
    assert snapshot(s)["comparison"] is None


def test_normal_demo_and_stress_are_honest_end_to_end():
    workspaces = Workspaces()
    normal = workspaces.create()
    assert replan(normal)
    assert normal.optimized.validated
    assert normal.optimized.metrics["unserved_kwh"] < 1e-5
    assert snapshot(normal)["comparison"]["cost_savings_eur"] >= 0
    stress = workspaces.create(stress=True)
    assert replan(stress)
    assert stress.optimized.validated
    assert stress.optimized.metrics["unserved_kwh"] >= 54.5 - 1e-4
    assert stress.optimized.metrics["target_success_percent"] < 100
