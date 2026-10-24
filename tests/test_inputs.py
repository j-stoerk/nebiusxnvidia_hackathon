import pytest

from backend.app.services.csv_validator import InputError, check_scenario, parse_prices, parse_sessions

HEADER = "vehicle_id,arrival_time,departure_time,energy_required_kwh,max_charging_power_kw\n"
VALID = "EV-1,2026-10-24T00:00:00Z,2026-10-24T01:00:00Z,1,2\n"


def test_utf8_bom_and_timezones():
    rows = parse_sessions(("\ufeff" + HEADER + VALID.replace("00:00:00Z", "02:00:00+02:00")).encode())
    assert rows[0].arrival_time.hour == 0


@pytest.mark.parametrize("content", [
    b"", b"\xff", b"vehicle_id\nEV-1\n", (HEADER + VALID + VALID).encode(),
    (HEADER + VALID.replace(",1,2", ",nan,2")).encode(),
    (HEADER + VALID.replace(",1,2", ",inf,2")).encode(),
    (HEADER + VALID.replace(",1,2", ",-1,2")).encode(),
    (HEADER + VALID.replace(",1,2", ",1,0")).encode(),
    (HEADER + VALID.replace("T00:00:00Z", "T00:00:00")).encode(),
    (HEADER + VALID.replace("2026-10-24T00:00:00Z", "123")).encode(),
    (HEADER + VALID.replace("T01:00:00Z", "T00:00:00Z")).encode(),
    (HEADER + VALID.replace("EV-1", " ")).encode(),
    (HEADER + "extra," + VALID).encode(),
    (HEADER.replace("vehicle_id", "vehicle_id,vehicle_id") + VALID).encode(),
])
def test_bad_upload_is_rejected(content):
    with pytest.raises(InputError):
        parse_sessions(content)


def test_row_errors_are_actionable():
    with pytest.raises(InputError) as error:
        parse_sessions((HEADER + VALID.replace(",1,2", ",bad,2")).encode())
    assert error.value.errors[0]["row"] == 2
    assert error.value.errors[0]["column"] == "energy_required_kwh"


def test_infeasible_energy_is_valid_input():
    assert parse_sessions((HEADER + VALID.replace(",1,2", ",60,2")).encode())[0].energy_required_kwh == 60


def test_price_coverage_and_duplicates(small_scenario):
    s = small_scenario
    with pytest.raises(InputError, match="Missing"):
        check_scenario(s.sessions, s.station, s.prices[:-1])
    with pytest.raises(InputError, match="Duplicate"):
        parse_prices(b"timestamp,price_eur_per_kwh\n2026-10-24T00:00Z,0.1\n2026-10-24T00:00Z,0.2\n")


def test_negative_prices_are_valid():
    prices = parse_prices(b"timestamp,price_eur_per_kwh\n2026-10-24T00:00Z,-0.1\n")
    assert prices[0].price_eur_per_kwh == -.1
