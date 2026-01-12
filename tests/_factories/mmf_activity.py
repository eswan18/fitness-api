from typing import Any, Mapping

from datetime import date

from fitness.load.mmf import MmfActivity


class MmfActivityFactory:
    def __init__(self, activity: MmfActivity | None = None):
        if activity is None:
            activity = MmfActivity(
                date_submitted=date(2023, 10, 1),
                workout_date=date(2023, 10, 1),
                activity_type="Run",
                calories_burned=500,
                distance=6,
                workout_time=3600,
                avg_pace=10,
                max_pace=5,
                avg_speed=6,
                max_speed=10,
                avg_heart_rate=150,
                steps=1000,
                notes="",
                source="abc",
                link="https://example.com",
            )
        self.activity = activity

    def make(self, update: Mapping[str, Any] | None = None) -> MmfActivity:
        return self.activity.model_copy(deep=True, update=update)
