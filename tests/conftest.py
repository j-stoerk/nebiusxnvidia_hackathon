import pytest

from backend.app.services import schedule_service


@pytest.fixture(autouse=True)
def fresh_state():
    schedule_service.reset_state()
    yield
    schedule_service.reset_state()
