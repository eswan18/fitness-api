from typing import Literal, Self, Optional
from datetime import date

from pydantic import BaseModel, model_validator

from .env_loader import EnvironmentName


Sex = Literal["M", "F"]  # Biological sex used for HR-based training load formulas


class LoadSeries(BaseModel):
    """A single training load series with name and data points."""

    name: str
    data: list[tuple[str, float]]  # [date_string, value] for Highcharts datetime axis


class TrmnlSummary(BaseModel):
    """Response model for the summary endpoint."""

    miles_all_time: float
    minutes_all_time: float
    miles_this_calendar_month: float
    days_this_calendar_month: int
    calendar_month_name: str
    miles_this_calendar_year: float
    days_this_calendar_year: int
    calendar_year: int
    miles_last_30_days: float
    miles_last_365_days: float
    load_data: list[LoadSeries]


class DayMileage(BaseModel):
    """Mileage aggregated for a single day."""

    date: date
    mileage: float

    def __lt__(self, other: Self) -> bool:
        return self.date < other.date


class WeekMileage(BaseModel):
    """Mileage aggregated for a single week.

    `week_start` is the first day of the week (Monday or Sunday depending on
    the requested week convention).
    """

    week_start: date
    mileage: float

    def __lt__(self, other: Self) -> bool:
        return self.week_start < other.week_start


class RetireShoeRequest(BaseModel):
    """Request model to retire a shoe on a specific date."""

    retired_at: date
    retirement_notes: Optional[str] = None


class CreateShoeRequest(BaseModel):
    """Request model for creating a shoe via POST."""

    name: str
    first_warning_mileage: int = 300
    second_warning_mileage: int = 500
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _check_warning_order(self) -> Self:
        if self.second_warning_mileage < self.first_warning_mileage:
            raise ValueError(
                "second_warning_mileage must be >= first_warning_mileage"
            )
        return self


class UpdateShoeRequest(BaseModel):
    """Request model for updating shoe properties via PATCH.

    All fields are optional. The router distinguishes "field omitted" from
    "field explicitly set to null" via ``model_fields_set`` so that, for example,
    a name-only edit does not unretire a shoe (a sent ``retired_at=null`` is what
    unretires it). The warning-mileage ordering (second >= first) is validated in
    the router against the shoe's resulting values, since either may be omitted.
    """

    name: Optional[str] = None
    first_warning_mileage: Optional[int] = None
    second_warning_mileage: Optional[int] = None
    retired_at: Optional[date] = None
    retirement_notes: Optional[str] = None


class MergeShoesRequest(BaseModel):
    """Request model for merging two shoes."""

    keep_shoe_id: str
    merge_shoe_id: str


class EnvironmentResponse(BaseModel):
    """Response model for the environment endpoint."""

    environment: EnvironmentName
