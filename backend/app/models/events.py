"""Simulated station and price events."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..utils.datetime_utils import ensure_utc


class EventType(str, Enum):
    CHARGER_FAILED = "CHARGER_FAILED"
    CHARGER_RECOVERED = "CHARGER_RECOVERED"
    PRICE_CHANGED = "PRICE_CHANGED"


class SimulationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=100)
    type: Literal["CHARGER_FAILED", "CHARGER_RECOVERED", "PRICE_CHANGED"]
    charger_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    time: datetime | None = None
    add_eur_per_kwh: float | None = Field(default=None, ge=-10, le=100)
    simulated: bool = True

    @field_validator("start_time", "end_time", "time", mode="before")
    @classmethod
    def parse_times(cls, value):
        if value is None or value == "":
            return None
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.type in ("CHARGER_FAILED", "CHARGER_RECOVERED") and not self.charger_id:
            raise ValueError("charger_id is required for charger events")
        if self.type == "CHARGER_FAILED":
            if not self.start_time or not self.end_time or self.end_time <= self.start_time:
                raise ValueError("CHARGER_FAILED needs start_time < end_time")
        if self.type == "CHARGER_RECOVERED" and not self.time:
            raise ValueError("CHARGER_RECOVERED needs time")
        if self.type == "PRICE_CHANGED":
            if self.add_eur_per_kwh is None:
                raise ValueError("PRICE_CHANGED needs add_eur_per_kwh")
            if not self.start_time or not self.end_time or self.end_time <= self.start_time:
                raise ValueError("PRICE_CHANGED needs start_time < end_time")
        return self
