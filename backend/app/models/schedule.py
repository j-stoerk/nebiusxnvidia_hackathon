"""Schedule allocations and metrics."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Allocation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    vehicle_id: str
    charger_id: str
    start_time: datetime
    end_time: datetime
    power_kw: float = Field(ge=0)
    charging_efficiency: float = Field(default=1, gt=0, le=1)


class VehicleMetric(BaseModel):
    vehicle_id: str
    required_kwh: float
    delivered_kwh: float
    shortfall_kwh: float
    target_met: bool
    arrival_time: datetime
    departure_time: datetime
    battery_capacity_kwh: float | None = None
    initial_soc: float | None = None
    requested_soc: float | None = None
    final_soc: float | None = None
    charger_id: str | None = None


class PowerPoint(BaseModel):
    timestamp: datetime
    power_kw: float
    price_eur_per_kwh: float


class ScheduleMetrics(BaseModel):
    cost_eur: float
    energy_cost_eur: float = 0.0
    demand_cost_eur: float = 0.0
    peak_power_kw: float
    prior_peak_kw: float = 0.0
    demand_tariff_eur_per_kw: float = 0.0
    charging_efficiency: float = 1.0
    delivered_kwh: float
    unserved_kwh: float
    target_success_percent: float
    vehicles: list[VehicleMetric]
    power_series: list[PowerPoint]
    billing_peaks_kw: dict[str, float] = Field(default_factory=dict)


class ScheduleResult(BaseModel):
    kind: Literal["baseline", "optimized"]
    allocations: list[Allocation]
    metrics: ScheduleMetrics
    solver_status: str
    runtime_seconds: float
    validated: bool = False
    shortfall_optimal: bool = False
    peak_optimal: bool = False
    cost_optimal: bool = False
