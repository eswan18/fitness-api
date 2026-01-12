from datetime import date
from typing import Self
from pydantic import BaseModel


class TrainingLoad(BaseModel):
    atl: float
    ctl: float
    tsb: float


class DayTrainingLoad(BaseModel):
    date: date
    training_load: TrainingLoad

    def __lt__(self, other: Self) -> bool:
        return self.date < other.date
