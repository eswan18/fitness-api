"""Hevy API client for fetching workout data."""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Optional

import httpx

from .models import (
    HevyWorkout,
    HevyExerciseTemplate,
    HevyWorkoutsResponse,
    HevyExerciseTemplatesResponse,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hevyapp.com"
WORKOUTS_URL = f"{BASE_URL}/v1/workouts"
WORKOUT_COUNT_URL = f"{BASE_URL}/v1/workouts/count"
EXERCISE_TEMPLATES_URL = f"{BASE_URL}/v1/exercise_templates"


@dataclass
class HevyClient:
    """Client for interacting with the Hevy API.

    Requires a Hevy PRO subscription to obtain an API key.
    Get your key at: https://hevy.com/settings?developer
    """

    api_key: str

    def _auth_headers(self) -> dict[str, str]:
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _make_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[httpx.Response]:
        """Make an API request to Hevy."""
        kwargs.setdefault("timeout", 30)

        with httpx.Client() as client:
            response = client.request(
                method, url, headers=self._auth_headers(), **kwargs
            )

            if response.status_code == 401:
                logger.error("Hevy API returned 401 Unauthorized - check your API key")
                return None

            if response.status_code == 429:
                logger.warning("Hevy API rate limit exceeded")
                return None

            return response

    def get_workout_count(self) -> int:
        """Get the total number of workouts."""
        response = self._make_request("GET", WORKOUT_COUNT_URL)

        if response is None:
            logger.error("Failed to fetch workout count")
            return 0

        if response.status_code != 200:
            logger.error(
                f"Hevy API error fetching workout count: {response.status_code} {response.text}"
            )
            return 0

        data = response.json()
        return data.get("workout_count", 0)

    def get_workouts(
        self,
        page: int = 1,
        page_size: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[HevyWorkout]:
        """Get workouts from Hevy API.

        Args:
            page: Page number (1-indexed)
            page_size: Number of workouts per page (max 10)
            since: Only return workouts after this datetime
            until: Only return workouts before this datetime

        Returns:
            List of HevyWorkout objects
        """
        params: dict[str, str | int] = {
            "page": page,
            "pageSize": min(page_size, 10),  # Hevy API max is 10
        }

        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        logger.debug(f"Fetching Hevy workouts: page={page}, params={params}")

        response = self._make_request("GET", WORKOUTS_URL, params=params)

        if response is None:
            logger.error(f"Failed to fetch workouts page {page}")
            return []

        if response.status_code != 200:
            logger.error(
                f"Hevy API error on page {page}: {response.status_code} {response.text}"
            )
            return []

        data = response.json()
        parsed = HevyWorkoutsResponse.model_validate(data)
        logger.debug(f"Received {len(parsed.workouts)} workouts from page {page}")
        return parsed.workouts

    def get_all_workouts(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> list[HevyWorkout]:
        """Get all workouts, handling pagination automatically.

        Args:
            since: Only return workouts after this datetime
            until: Only return workouts before this datetime

        Returns:
            List of all HevyWorkout objects
        """
        all_workouts: list[HevyWorkout] = []
        page = 1
        page_size = 10  # Hevy API max

        logger.info("Fetching all workouts from Hevy API")

        while True:
            workouts = self.get_workouts(
                page=page, page_size=page_size, since=since, until=until
            )

            if not workouts:
                break

            all_workouts.extend(workouts)
            logger.debug(
                f"Fetched page {page}: {len(workouts)} workouts "
                f"(total so far: {len(all_workouts)})"
            )

            if len(workouts) < page_size:
                # Last page
                break

            page += 1

        logger.info(f"Completed fetching {len(all_workouts)} workouts from Hevy")
        return all_workouts

    def get_exercise_templates(
        self, page: int = 1, page_size: int = 100
    ) -> list[HevyExerciseTemplate]:
        """Get exercise templates from Hevy API.

        Args:
            page: Page number (1-indexed)
            page_size: Number of templates per page (max 100)

        Returns:
            List of HevyExerciseTemplate objects
        """
        params = {
            "page": page,
            "pageSize": min(page_size, 100),  # Hevy API max is 100
        }

        logger.debug(f"Fetching Hevy exercise templates: page={page}")

        response = self._make_request("GET", EXERCISE_TEMPLATES_URL, params=params)

        if response is None:
            logger.error(f"Failed to fetch exercise templates page {page}")
            return []

        if response.status_code != 200:
            logger.error(
                f"Hevy API error fetching templates page {page}: "
                f"{response.status_code} {response.text}"
            )
            return []

        data = response.json()
        parsed = HevyExerciseTemplatesResponse.model_validate(data)
        logger.debug(
            f"Received {len(parsed.exercise_templates)} templates from page {page}"
        )
        return parsed.exercise_templates

    def get_all_exercise_templates(self) -> list[HevyExerciseTemplate]:
        """Get all exercise templates, handling pagination automatically.

        Returns:
            List of all HevyExerciseTemplate objects
        """
        all_templates: list[HevyExerciseTemplate] = []
        page = 1
        page_size = 100  # Hevy API max

        logger.info("Fetching all exercise templates from Hevy API")

        while True:
            templates = self.get_exercise_templates(page=page, page_size=page_size)

            if not templates:
                break

            all_templates.extend(templates)

            if len(templates) < page_size:
                # Last page
                break

            page += 1

        logger.info(f"Completed fetching {len(all_templates)} exercise templates")
        return all_templates
