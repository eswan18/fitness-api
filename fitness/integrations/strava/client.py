from typing import Iterable
from dataclasses import dataclass
import logging

import httpx

from fitness.db.oauth_credentials import OAuthCredentials, upsert_credentials
from .models import StravaActivity, StravaGear, activity_list_adapter
from .auth import refresh_access_token

logger = logging.getLogger(__name__)

GEAR_URL = "https://www.strava.com/api/v3/gear"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
ATHLETE_URL = "https://www.strava.com/api/v3/athlete"


@dataclass
class StravaClient:
    creds: OAuthCredentials

    def needs_token_refresh(self) -> bool:
        """Check if the client's access token needs to be refreshed."""
        return (
            self.creds.is_access_token_valid() is not None
            and not self.creds.is_access_token_valid()
        )

    async def refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        token = await refresh_access_token(self.creds.refresh_token)
        new_creds = OAuthCredentials(
            provider="strava",
            client_id=self.creds.client_id,
            client_secret=self.creds.client_secret,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.expires_at_datetime(),
        )
        upsert_credentials(new_creds)
        self.creds = new_creds
        logger.info("Refreshed Strava access token and updated credentials in database")

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.creds.access_token}",
        }

    def get_activities(self) -> list[StravaActivity]:
        """Get the activities from the Strava API."""
        raw_activities = self._get_activities_raw()
        activities = activity_list_adapter.validate_python(raw_activities)
        return activities

    def _get_activities_raw(self) -> list[dict]:
        """Get the activity data from the Strava API.

        Handles pagination until no more pages are returned.
        """
        page = 1
        per_page = 200
        activities: list[dict] = []
        logger.info(f"Fetching activities from Strava API (page size: {per_page})")

        while True:
            params = {"per_page": per_page, "page": page}
            logger.debug(f"Requesting Strava activities page {page}: {params}")

            try:
                response = httpx.get(
                    ACTIVITIES_URL,
                    headers=self._auth_headers(),
                    params=params,
                    timeout=20,  # This request is often *extremely* slow
                )
                response.raise_for_status()
                payload: list[dict] = response.json()

                logger.debug(f"Received {len(payload)} activities from page {page}")
                activities.extend(payload)

                if len(payload) == 0:
                    # This indicates there are no more activities to fetch.
                    logger.info(
                        f"Completed fetching activities: {len(activities)} total activities across {page - 1} pages"
                    )
                    break

                page += 1

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Strava API returned error on page {page}: {e.response.status_code} {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(
                    f"Failed to connect to Strava API on page {page}: {type(e).__name__}: {str(e)}"
                )
                raise

        return activities

    def get_gear(self, gear_ids: Iterable[str]) -> list[StravaGear]:
        """Get the gear from the Strava API."""
        raw_gear = self._get_gear_raw(gear_ids)
        gear = [StravaGear.model_validate(g) for g in raw_gear]
        return gear

    def _get_gear_raw(self, gear_ids: Iterable[str]) -> list[dict]:
        """Get the gear data from the Strava API."""
        gear: list[dict] = []
        gear_id_list = list(gear_ids)

        logger.info(f"Fetching {len(gear_id_list)} gear items from Strava API")

        for idx, id in enumerate(gear_id_list, start=1):
            logger.debug(f"Fetching gear {idx}/{len(gear_id_list)}: {id}")

            try:
                response = httpx.get(
                    f"{GEAR_URL}/{id}", headers=self._auth_headers(), timeout=10
                )
                response.raise_for_status()
                payload_gear = response.json()
                gear.append(payload_gear)

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Strava API returned error for gear {id}: {e.response.status_code} {e.response.text}"
                )
                raise
            except httpx.RequestError as e:
                logger.error(
                    f"Failed to fetch gear {id} from Strava API: {type(e).__name__}: {str(e)}"
                )
                raise

        logger.info(f"Successfully fetched {len(gear)} gear items from Strava API")
        return gear
