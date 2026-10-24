from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models import Charger, Price, Session, Station
from backend.app.services.scenario import Scenario


@pytest.fixture
def small_scenario():
    start = datetime(2026, 10, 24, tzinfo=timezone.utc)
    return Scenario("test", [Session(vehicle_id="EV-1", arrival_time=start, departure_time=start + timedelta(hours=1),
                                    energy_required_kwh=1, max_charging_power_kw=2)],
                    Station(fixed_connections=False, station_power_limit_kw=2, chargers=[Charger(charger_id="C1", max_power_kw=2)]),
                    [Price(timestamp=start + timedelta(minutes=15 * i), price_eur_per_kwh=p) for i, p in enumerate([1, 1, .1, .1])])
