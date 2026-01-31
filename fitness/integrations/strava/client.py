from typing import Iterable, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

import httpx

from fitness.db.oauth_credentials import OAuthCredentials, upsert_credentials
from .models import StravaActivity, StravaGear, activity_list_adapter
from .auth import refresh_access_token_sync

logger = logging.getLogger(__name__)

GEAR_URL = "https://www.strava.com/api/v3/gear"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
ATHLETE_URL = "https://www.strava.com/api/v3/athlete"


@dataclass
class StravaClient:
    creds: OAuthCredentials

    def needs_token_refresh(self) -> bool:
        """Check if the access token needs to be refreshed.

        Returns:
            True if token is expired or expires within 5 minutes, False otherwise.
        """
        if self.creds.expires_at is None:
            # If we don't know expiration, we can't proactively refresh
            return False

        # Ensure expires_at is timezone-aware
        expires_at_aware = self.creds.expires_at
        if expires_at_aware.tzinfo is None:
            expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        # Refresh if token expires within the next 5 minutes
        return expires_at_aware <= now + timedelta(minutes=5)

    def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token and persist to database.

        Returns:
            True if refresh was successful, False otherwise.
            Raises ValueError if refresh token is revoked/expired.
        """
        try:
            token = refresh_access_token_sync(self.creds.refresh_token)
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
            logger.info(
                "Successfully refreshed Strava access token and persisted to database"
            )
            return True
        except ValueError:
            # Re-raise ValueError (invalid_grant) so callers can handle it
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error refreshing Strava access token: "
                f"exception_type={type(e).__name__}, error={e}"
            )
            return False

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.creds.access_token}",
        }

    def _make_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[httpx.Response]:
        """Make an API request with automatic token refresh on 401 or if token is expired."""
        # Proactively refresh token if it's expired or about to expire
        if self.needs_token_refresh():
            logger.info(
                "Strava access token expired or about to expire, refreshing proactively..."
            )
            try:
                if not self._refresh_access_token():
                    logger.error(
                        f"Failed to refresh token proactively before {method} request to {url}"
                    )
                    # Continue anyway - might still work, or will get 401
            except ValueError as e:
                # Refresh token is revoked/expired - cannot proceed
                logger.error(
                    f"Cannot refresh token for {method} request to {url}: "
                    f"exception_type={type(e).__name__}, error={e}"
                )
                return None

        # Set default timeout if not provided
        kwargs.setdefault("timeout", 10)

        with httpx.Client() as client:
            response = client.request(
                method, url, headers=self._auth_headers(), **kwargs
            )

            # If unauthorized, try to refresh token and retry once
            if response.status_code == 401:
                logger.warning(
                    f"Received 401 Unauthorized for {method} request to {url}, "
                    f"attempting token refresh and retry"
                )
                try:
                    if self._refresh_access_token():
                        # Retry with new token
                        response = client.request(
                            method, url, headers=self._auth_headers(), **kwargs
                        )
                        logger.info(
                            f"Successfully retried {method} request to {url} after token refresh, "
                            f"status_code={response.status_code}"
                        )
                    else:
                        logger.error(
                            f"Failed to refresh token after 401, cannot retry {method} request to {url}"
                        )
                        return response
                except ValueError as e:
                    # Refresh token is revoked/expired - cannot retry
                    logger.error(
                        f"Cannot refresh token after 401 for {method} request to {url}: "
                        f"exception_type={type(e).__name__}, error={e}"
                    )
                    return None

            return response

    def get_activities(self, after: Optional[datetime] = None) -> list[StravaActivity]:
        """Get the activities from the Strava API.

        Args:
            after: Only return activities after this datetime (for incremental sync).
        """
        raw_activities = self._get_activities_raw(after=after)
        activities = activity_list_adapter.validate_python(raw_activities)
        return activities

    def _get_activities_raw(self, after: Optional[datetime] = None) -> list[dict]:
        """Get the activity data from the Strava API.

        Handles pagination until no more pages are returned.

        Args:
            after: Only return activities after this datetime (epoch timestamp).
        """
        page = 1
        per_page = 200
        activities: list[dict] = []

        if after:
            logger.info(
                f"Fetching activities from Strava API after {after.isoformat()} "
                f"(page size: {per_page})"
            )
        else:
            logger.info(
                f"Fetching all activities from Strava API (page size: {per_page})"
            )

        while True:
            params: dict[str, int] = {"per_page": per_page, "page": page}
            if after:
                # Strava expects epoch timestamp (seconds since 1970-01-01)
                params["after"] = int(after.timestamp())
            logger.debug(f"Requesting Strava activities page {page}: {params}")

            response = self._make_request(
                "GET",
                ACTIVITIES_URL,
                params=params,
                timeout=20,  # This request is often *extremely* slow
            )

            if response is None:
                logger.error(
                    f"Failed to fetch activities page {page}: no response (token refresh may have failed)"
                )
                raise httpx.RequestError(
                    "Failed to fetch activities - token refresh failed"
                )

            if response.status_code != 200:
                logger.error(
                    f"Strava API returned error on page {page}: {response.status_code} {response.text}"
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

            response = self._make_request("GET", f"{GEAR_URL}/{id}")

            if response is None:
                logger.error(
                    f"Failed to fetch gear {id}: no response (token refresh may have failed)"
                )
                raise httpx.RequestError(
                    f"Failed to fetch gear {id} - token refresh failed"
                )

            if response.status_code != 200:
                logger.error(
                    f"Strava API returned error for gear {id}: {response.status_code} {response.text}"
                )
                response.raise_for_status()

            payload_gear = response.json()
            gear.append(payload_gear)

        logger.info(f"Successfully fetched {len(gear)} gear items from Strava API")
        return gear
