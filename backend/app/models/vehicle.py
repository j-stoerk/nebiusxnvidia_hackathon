"""Vehicle charging session model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..utils.datetime_utils import ensure_utc


class VehicleSession(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    vehicle_id: str = Field(min_length=1, max_length=80)
    arrival_time: datetime
    departure_time: datetime
    energy_required_kwh: float = Field(ge=0, le=1000)
    max_charging_power_kw: float = Field(gt=0, le=1000)
    charger_id: str | None = Field(default=None, min_length=1, max_length=80)
    connector_type: str = Field(default="Type2", min_length=1, max_length=40)
    battery_capacity_kwh: float | None = Field(default=None, gt=0, le=2000)
    initial_soc: float | None = Field(default=None, ge=0, le=1)
    requested_soc: float | None = Field(default=None, ge=0, le=1)
    transition_soc: float = Field(default=.8, gt=0, lt=1)

    @field_validator("arrival_time", "departure_time", mode="before")
    @classmethod
    def parse_times(cls, value):
        return ensure_utc(value)

    @field_validator("vehicle_id")
    @classmethod
    def strip_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("vehicle_id must not be blank")
        return value

    @model_validator(mode="after")
    def check_window(self):
        if self.departure_time <= self.arrival_time:
            raise ValueError("departure_time must be after arrival_time")
        has_cap = self.battery_capacity_kwh is not None
        has_init = self.initial_soc is not None
        if has_cap != has_init:
            raise ValueError("battery_capacity_kwh and initial_soc must be provided together")
        if has_cap and has_init:
            headroom = self.battery_capacity_kwh * (1.0 - self.initial_soc)
            if self.energy_required_kwh > headroom + 1e-6:
                raise ValueError("energy_required_kwh exceeds battery headroom from initial_soc")
            if self.requested_soc is None:
                self.requested_soc = min(
                    1.0, self.initial_soc + self.energy_required_kwh / self.battery_capacity_kwh
                )
            elif self.requested_soc + 1e-6 < self.initial_soc:
                raise ValueError("requested_soc must be >= initial_soc")
            elif abs(self.battery_capacity_kwh * (self.requested_soc - self.initial_soc) - self.energy_required_kwh) > 1e-6:
                raise ValueError("requested_soc conflicts with the declared battery energy target")
        elif self.requested_soc is not None:
            raise ValueError("requested_soc requires capacity and initial_soc")
        return self
