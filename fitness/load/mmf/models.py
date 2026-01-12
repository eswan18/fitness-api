from typing import Annotated, Literal
from datetime import date, datetime
from pydantic import AliasChoices
import re

from pydantic import BaseModel, Field, BeforeValidator

# There are some cases where the shoe names are inconsistent in the data.
# This remaps them to a consistent name.
SHOE_RENAME_MAP = {
    "M1080K10": "New Balance M1080K10",
    "M1080R10": "New Balance M1080R10",
    "New Balance 1080K10": "New Balance M1080K10",
    "Karhu Fusion 2021  2": "Karhu Fusion 2021 - 2",
    "Karhu Fusion 2021 2": "Karhu Fusion 2021 - 2",
    "Adidas Boston 13": "Boston 13",
}

MmfActivityType = Literal[
    "Bike Ride",
    "Gym Workout",
    "Indoor Run / Jog",
    "Machine Workout",
    "Run",
    "Walk",
    "Weight Workout",
]


def empty_str_to_none(v: str) -> str | None:
    """
    Convert an empty string to None, or leave the value as is.

    A few numeric fields comes in as empty strings when they're not set. Pydantic throws
    type errors if we don't convert them.
    """
    if v == "":
        return None
    return v


def parse_date(v: str | date) -> date:
    """
    Convert a date string in the format 'May 6, 2025' to a proper date object.

    Dates come in as 'May 6, 2025' or 'Jan. 14, 2025' or 'Sept. 24, 2024' but Pydantic
    expects 'YYYY-MM-DD'.
    """
    if isinstance(v, date):
        return v
    # 1) Strip any dots on month abbreviations
    clean = v.replace(".", "")  # remove any trailing dots on abbreviations
    # 2) Normalize "Sept" -> "Sep" (so it matches %b)
    clean = re.sub(r"\bSept\b", "Sep", clean, flags=re.IGNORECASE)
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date string not in expected format: {v!r}")


class MmfActivity(BaseModel):
    date_submitted: Annotated[date, BeforeValidator(parse_date)] = Field(
        validation_alias=AliasChoices("date_submitted", "Date Submitted")
    )
    workout_date: Annotated[date, BeforeValidator(parse_date)] = Field(
        validation_alias=AliasChoices("workout_date", "Workout Date"),
    )
    workout_date_utc: date | None = None  # Set during loading after timezone conversion
    activity_type: MmfActivityType = Field(
        validation_alias=AliasChoices("activity_type", "Activity Type")
    )
    calories_burned: float = Field(
        validation_alias=AliasChoices("calories_burned", "Calories Burned (kCal)")
    )
    distance: float = Field(validation_alias=AliasChoices("distance", "Distance (mi)"))
    workout_time: float = Field(
        validation_alias=AliasChoices("workout_time", "Workout Time (seconds)")
    )
    avg_pace: float = Field(
        validation_alias=AliasChoices("avg_pace", "Avg Pace (min/mi)")
    )
    max_pace: float = Field(
        validation_alias=AliasChoices("max_pace", "Max Pace (min/mi)")
    )
    avg_speed: float = Field(
        validation_alias=AliasChoices("avg_speed", "Avg Speed (mi/h)")
    )
    max_speed: float = Field(
        validation_alias=AliasChoices("max_speed", "Max Speed (mi/h)")
    )
    avg_heart_rate: Annotated[float | None, BeforeValidator(empty_str_to_none)] = Field(
        validation_alias=AliasChoices("avg_heart_rate", "Avg Heart Rate"),
    )
    steps: Annotated[int | None, BeforeValidator(empty_str_to_none)] = Field(
        validation_alias=AliasChoices("steps", "Steps"),
    )
    notes: str = Field(validation_alias=AliasChoices("notes", "Notes"))
    source: str = Field(validation_alias=AliasChoices("source", "Source"))
    link: str = Field(validation_alias=AliasChoices("link", "Link"))

    def shoes(self) -> str | None:
        """
        Extract the shoes from the notes field.

        Shoes are in the format 'Shoes: <shoe name>'.
        """
        match = re.search(r"Shoes:\s*(.+)", self.notes)
        if match:
            raw_shoe_name = match.group(1).strip()
            if raw_shoe_name in SHOE_RENAME_MAP:
                # If the shoe name is in the rename mapping, use the mapped name
                return SHOE_RENAME_MAP[raw_shoe_name]
            else:
                return raw_shoe_name
        return None
