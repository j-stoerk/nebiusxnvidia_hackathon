from backend.app.models import SimulationEvent
from backend.app.services import schedule_service


def test_price_event_and_reoptimize():
    schedule_service.load_demo_if_empty()
    event = SimulationEvent(
        event_id="test-price-1",
        type="PRICE_CHANGED",
        start_time="2026-10-24T09:00:00Z",
        end_time="2026-10-24T10:00:00Z",
        add_eur_per_kwh=0.15,
        simulated=True,
    )
    result = schedule_service.simulate(event, reoptimize=True)
    assert result["event_result"]["applied"] is True
    assert result["optimized"] is not None
    assert result["comparison"] is not None
