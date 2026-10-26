"""Station configuration, demand tariff, and electricity prices."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..utils.datetime_utils import ensure_utc


class Charger(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    charger_id: str = Field(min_length=1, max_length=80)
    max_power_kw: float = Field(gt=0, le=1000)
    connector_type: str = Field(default="Type2", min_length=1, max_length=40)
    available: bool = True
    simulated: bool = True


class DemandTariff(BaseModel):
    """Incremental demand charge above prior billing peak (simulated)."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    eur_per_kw: float = Field(default=0, ge=0, le=10000)
    period: Literal["month", "year"] = "month"
    timezone: Literal["UTC", "Europe/Berlin"] = "Europe/Berlin"
    prior_peak_kw: float = Field(default=0.0, ge=0, le=100000)
    prior_peaks_kw: dict[str, float] = Field(default_factory=dict, max_length=24)

    @model_validator(mode="after")
    def valid_peaks(self):
        import math
        import re
        pattern = r"\d{4}-(?:0[1-9]|1[0-2])" if self.period == "month" else r"\d{4}"
        if any(not re.fullmatch(pattern, k) or not math.isfinite(v) or not 0 <= v <= 100000 for k, v in self.prior_peaks_kw.items()):
            raise ValueError("Prior peaks need matching YYYY-MM/YYYY keys and finite nonnegative kW")
        return self


class PricePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    timestamp: datetime
    price_eur_per_kwh: float = Field(ge=-10, le=100)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_time(cls, value):
        return ensure_utc(value)


class StationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    simulated: bool = True
    station_id: str = "DEMO-01"
    timezone: Literal["UTC"] = "UTC"
    slot_minutes: Literal[15] = 15
    station_power_limit_kw: float = Field(gt=0, le=10000)
    charger_count: int = Field(default=10, ge=1)
    charger_max_power_kw: float = Field(default=11.0, gt=0, le=1000)
    charging_efficiency: float = Field(default=1.0, gt=0, le=1)
    fixed_connections: bool = True
    optimization_goal: Literal["cost", "peak"] = "cost"
    demand_tariff: DemandTariff = Field(default_factory=DemandTariff)
    chargers: list[Charger] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_chargers(self):
        if not self.chargers:
            self.chargers = [
                Charger(
                    charger_id=f"CH-{i:02d}",
                    max_power_kw=self.charger_max_power_kw,
                    available=True,
                    simulated=True,
                )
                for i in range(1, self.charger_count + 1)
            ]
        else:
            self.charger_count = len(self.chargers)
        if len({c.charger_id for c in self.chargers}) != len(self.chargers):
            raise ValueError("Charger IDs must be unique")
        return self
