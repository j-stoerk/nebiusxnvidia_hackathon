"""Validated API contracts. All powers are grid-side kW, energy targets battery-side kWh."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


def utc(value: datetime) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Use an ISO 8601 timestamp with an explicit timezone") from exc
    if not isinstance(value, datetime):
        raise ValueError("Use an ISO 8601 timestamp with an explicit timezone")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must include a timezone (Z or an explicit offset)")
    return value.astimezone(timezone.utc)


class Session(Contract):
    vehicle_id: str = Field(min_length=1, max_length=80)
    arrival_time: datetime
    departure_time: datetime
    energy_required_kwh: float = Field(ge=0, le=1000)
    max_charging_power_kw: float = Field(gt=0, le=1000)
    connector_type: str = Field(default="Type2", min_length=1, max_length=40)
    charger_id: str | None = Field(default=None, min_length=1, max_length=80)
    battery_capacity_kwh: float | None = Field(default=None, gt=0, le=2000)
    initial_soc: float | None = Field(default=None, ge=0, le=1)
    transition_soc: float = Field(default=0.8, gt=0, lt=1)

    _times = field_validator("arrival_time", "departure_time", mode="before")(utc)

    @field_validator("vehicle_id", "connector_type")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def interval(self):
        if self.departure_time <= self.arrival_time:
            raise ValueError("Departure must follow arrival")
        if (self.battery_capacity_kwh is None) != (self.initial_soc is None):
            raise ValueError("Taper needs both battery_capacity_kwh and initial_soc")
        if self.initial_soc is not None and self.energy_required_kwh > self.battery_capacity_kwh * (1 - self.initial_soc) + 1e-8:
            raise ValueError("Energy target exceeds battery headroom")
        return self


class Charger(Contract):
    charger_id: str = Field(min_length=1, max_length=80)
    max_power_kw: float = Field(gt=0, le=1000)
    connector_type: str = Field(default="Type2", min_length=1, max_length=40)
    available: bool = True


class DemandTariff(Contract):
    """Incremental 15-minute demand cost; not an entire utility bill."""
    eur_per_kw: float = Field(default=0, ge=0, le=10000)
    period: Literal["month", "year"] = "month"
    timezone: Literal["UTC", "Europe/Berlin"] = "Europe/Berlin"
    prior_peaks_kw: dict[str, float] = Field(default_factory=dict, max_length=24)

    @field_validator("prior_peaks_kw")
    @classmethod
    def peaks(cls, values):
        import re
        if any(not re.fullmatch(r"\d{4}(-(?:0[1-9]|1[0-2]))?", k) or not 0 <= v <= 100000 for k, v in values.items()):
            raise ValueError("Prior peaks need YYYY or YYYY-MM keys and nonnegative finite kW")
        return values

    @model_validator(mode="after")
    def matching_periods(self):
        length = 7 if self.period == "month" else 4
        if any(len(key) != length for key in self.prior_peaks_kw):
            raise ValueError("Prior peak keys must match the selected month/year period")
        return self


class Station(Contract):
    simulated: bool = True
    station_id: str = Field(default="DEMO-01", min_length=1, max_length=80)
    timezone: Literal["UTC"] = "UTC"
    slot_minutes: Literal[15] = 15
    station_power_limit_kw: float = Field(gt=0, le=10000)
    charging_efficiency: float = Field(default=1, gt=0, le=1)
    chargers: list[Charger] = Field(min_length=1, max_length=30)
    demand_tariff: DemandTariff = Field(default_factory=DemandTariff)
    fixed_connections: bool = True

    @model_validator(mode="after")
    def unique(self):
        if len({c.charger_id for c in self.chargers}) != len(self.chargers):
            raise ValueError("Charger IDs must be unique")
        return self


class Price(Contract):
    timestamp: datetime
    price_eur_per_kwh: float = Field(ge=-10, le=100)

    _time = field_validator("timestamp", mode="before")(utc)


class Event(Contract):
    event_id: str = Field(min_length=1, max_length=100)
    type: Literal["CHARGER_FAILED", "CHARGER_RECOVERED", "PRICE_CHANGED"]
    charger_id: str | None = Field(default=None, max_length=80)
    start_time: datetime | None = None
    end_time: datetime | None = None
    time: datetime | None = None
    add_eur_per_kwh: float | None = Field(default=None, ge=-10, le=100)

    @field_validator("start_time", "end_time", "time", mode="before")
    @classmethod
    def dates(cls, value):
        return utc(value) if value else value

    @model_validator(mode="after")
    def fields_for_type(self):
        if self.type in ("CHARGER_FAILED", "PRICE_CHANGED"):
            if self.start_time is None or self.end_time is None or self.end_time <= self.start_time:
                raise ValueError("Event needs start_time before end_time")
        if self.type.startswith("CHARGER") and not self.charger_id:
            raise ValueError("Charger event needs charger_id")
        if self.type == "CHARGER_RECOVERED" and self.time is None:
            raise ValueError("Recovery needs time")
        if self.type == "PRICE_CHANGED" and self.add_eur_per_kwh is None:
            raise ValueError("Price event needs add_eur_per_kwh")
        return self


class Allocation(Contract):
    vehicle_id: str
    charger_id: str
    start_time: datetime
    end_time: datetime
    power_kw: float = Field(gt=0)
    charging_efficiency: float = Field(default=1, gt=0, le=1)

    _dates = field_validator("start_time", "end_time", mode="before")(utc)

    @model_validator(mode="after")
    def positive_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("Allocation duration must be positive")
        return self


class Schedule(Contract):
    kind: Literal["baseline", "optimized"]
    allocations: list[Allocation]
    state_version: int
    schedule_version: int
    solver_status: str
    runtime_seconds: float
    shortfall_optimal: bool = False
    cost_optimal: bool = False
    validated: bool = False
    metrics: dict = Field(default_factory=dict)


class VersionRequest(Contract):
    expected_version: int = Field(ge=1)


class EventRequest(VersionRequest):
    event: Event


class AdvanceRequest(VersionRequest):
    time: datetime
    _time = field_validator("time", mode="before")(utc)


class SettingsRequest(VersionRequest):
    station: Station


class ChatRequest(VersionRequest):
    message: str = Field(min_length=1, max_length=4000)
    allow_changes: bool = False
