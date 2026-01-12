from typing import Any, Mapping
from datetime import datetime
from fitness.models import Run


class RunFactory:
    def __init__(self, run: Run | None = None):
        if run is None:
            run = Run(
                id="test_run_1",
                datetime_utc=datetime(2023, 10, 1, 12, 0, 0),
                type="Outdoor Run",
                distance=5.0,
                duration=1800,
                source="Strava",
                avg_heart_rate=150.0,
                shoe_id="test_shoe_id",
                deleted_at=None,
            )
            run._shoe_name = "Nike Test Shoe"
        self.run = run

    def make(self, update: Mapping[str, Any] | None = None) -> Run:
        run = self.run.model_copy(deep=True, update=update)
        # If date was updated, convert it to datetime_utc (assuming midnight UTC)
        if update and "date" in update and "datetime_utc" not in update:
            new_date = update["date"]
            update = dict(update)  # Create a copy
            update["datetime_utc"] = datetime.combine(new_date, datetime.min.time())
            del update["date"]  # Remove the date field since it doesn't exist anymore
            run = self.run.model_copy(deep=True, update=update)
        return run
