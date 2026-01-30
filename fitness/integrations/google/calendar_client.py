"""Google Calendar API client for syncing workout events."""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import httpx
from fitness.models.run import Run
from fitness.models.lift import Lift
from fitness.db.oauth_credentials import get_credentials, update_access_token

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""

    def __init__(self):
        """Initialize the client with credentials from database."""
        db_creds = get_credentials("google")

        if not db_creds:
            raise ValueError(
                "Google Calendar credentials not found in database. "
                "Please store credentials using the OAuth endpoint or upsert_credentials function."
            )

        logger.info("Loading Google OAuth credentials from database")
        self.client_id = db_creds.client_id
        self.client_secret = db_creds.client_secret
        self.access_token = db_creds.access_token
        self.refresh_token = db_creds.refresh_token
        self.expires_at = db_creds.expires_at

        if not all(
            [self.client_id, self.client_secret, self.access_token, self.refresh_token]
        ):
            raise ValueError(
                "Google Calendar credentials in database are incomplete. "
                "Missing required fields: client_id, client_secret, access_token, or refresh_token."
            )

        self.base_url = "https://www.googleapis.com/calendar/v3"
        # Allow selecting a specific calendar; default to primary.
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID") or "primary"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def needs_token_refresh(self) -> bool:
        """Check if the access token needs to be refreshed.

        Returns:
            True if token is expired or expiration is unknown, False otherwise.
        """
        if self.expires_at is None:
            # If we don't know expiration, we can't proactively refresh
            return False

        # Ensure expires_at is timezone-aware
        expires_at_aware = self.expires_at
        if expires_at_aware.tzinfo is None:
            expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        # Refresh if token expires within the next 5 minutes
        return expires_at_aware <= now + timedelta(minutes=5)

    def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token and persist to database.

        Returns:
            True if refresh was successful, False otherwise.
            Raises ValueError if refresh token is revoked/expired (invalid_grant error).
        """
        try:
            with httpx.Client() as client:
                response = client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.refresh_token,
                        "grant_type": "refresh_token",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code == 200:
                    token_data = response.json()
                    new_access_token = token_data["access_token"]

                    # Extract expiration time from expires_in (seconds)
                    expires_at = None
                    if "expires_in" in token_data:
                        expires_in_seconds = token_data["expires_in"]
                        expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=expires_in_seconds
                        )

                    # Google may return a new refresh token
                    new_refresh_token = token_data.get("refresh_token")

                    # Update in-memory tokens
                    self.access_token = new_access_token
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token
                        logger.info("Google provided a new refresh token")
                    if expires_at:
                        self.expires_at = expires_at

                    # Persist to database
                    try:
                        update_access_token(
                            "google",
                            new_access_token,
                            expires_at=expires_at,
                            refresh_token=new_refresh_token,
                        )
                        logger.info(
                            "Successfully refreshed Google access token and persisted to database"
                        )
                    except Exception as db_error:
                        logger.exception(
                            f"Failed to persist refreshed token to database: "
                            f"exception_type={type(db_error).__name__}, error={db_error}"
                        )
                        logger.warning(
                            "Token refreshed in memory but not persisted - may need to refresh again on restart"
                        )

                    return True
                else:
                    error_text = response.text
                    error_data = {}
                    try:
                        error_data = response.json()
                    except Exception as json_error:
                        # Failed to parse error response as JSON; proceed with empty error_data.
                        logger.warning(
                            f"Failed to parse token refresh error response as JSON: "
                            f"exception_type={type(json_error).__name__}, error={json_error}, "
                            f"raw_response={error_text[:500]}"
                        )

                    # Check for revoked/expired refresh token
                    if (
                        response.status_code == 400
                        and error_data.get("error") == "invalid_grant"
                    ):
                        logger.error(
                            f"Refresh token has been expired or revoked. "
                            f"Re-authorization required. status_code={response.status_code}, "
                            f"error_code={error_data.get('error')}, "
                            f"error_description={error_data.get('error_description', 'N/A')}"
                        )
                        # Raise a specific exception that callers can catch
                        raise ValueError(
                            "Refresh token expired or revoked. Re-authorization required."
                        )

                    logger.error(
                        f"Failed to refresh token: status_code={response.status_code}, "
                        f"error_data={error_data}, response_text={error_text[:500]}"
                    )
                    return False

        except ValueError:
            # Re-raise ValueError (invalid_grant) so callers can handle it
            raise
        except Exception as e:
            logger.exception(
                f"Unexpected error refreshing access token: "
                f"exception_type={type(e).__name__}, error={e}"
            )
            return False

    def _make_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[httpx.Response]:
        """Make an API request with automatic token refresh on 401 or if token is expired."""
        # Proactively refresh token if it's expired or about to expire
        if self.needs_token_refresh():
            logger.info(
                "Access token expired or about to expire, refreshing proactively..."
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

        headers = self._get_headers()
        kwargs.setdefault("headers", {}).update(headers)

        try:
            with httpx.Client() as client:
                response = client.request(method, url, **kwargs)

                # If unauthorized, try to refresh token and retry once
                if response.status_code == 401:
                    logger.warning(
                        f"Received 401 Unauthorized for {method} request to {url}, "
                        f"attempting token refresh and retry"
                    )
                    try:
                        if self._refresh_access_token():
                            # Update headers with new token and retry
                            kwargs["headers"].update(self._get_headers())
                            response = client.request(method, url, **kwargs)
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

        except Exception as e:
            logger.exception(
                f"Unexpected error making {method} request to {url}: "
                f"exception_type={type(e).__name__}, error={e}"
            )
            return None

    def create_workout_event(self, run: Run) -> Optional[str]:
        """Create a calendar event for a workout run.

        Args:
            run: The Run object to create an event for.

        Returns:
            Google Calendar event ID if successful, None otherwise.
        """
        # Format the event title
        distance_str = f"{run.distance:.1f}" if run.distance else "0.0"
        event_title = f"{distance_str} Mile {run.type or 'Run'}"

        # Convert stored UTC-naive datetime to timezone-aware UTC
        start_dt_utc = run.datetime_utc.replace(tzinfo=timezone.utc)

        # Use actual run duration for end time in UTC
        duration_seconds = int(run.duration)
        if duration_seconds < 0:
            duration_seconds = 0
        end_dt_utc = start_dt_utc + timedelta(seconds=duration_seconds)

        event_data = {
            "summary": event_title,
            "description": f"Workout synced from fitness app\nRun ID: {run.id}",
            "start": {
                # RFC3339 with explicit UTC offset
                "dateTime": start_dt_utc.isoformat(),
            },
            "end": {
                "dateTime": end_dt_utc.isoformat(),
            },
        }

        url = f"{self.base_url}/calendars/{self.calendar_id}/events"
        response = self._make_request("POST", url, json=event_data)

        if response and 200 <= response.status_code < 300:
            event = response.json()
            event_id = event.get("id")
            logger.info(
                f"Successfully created calendar event: run_id={run.id}, "
                f"event_id={event_id}, calendar_id={self.calendar_id}"
            )
            return event_id
        else:
            status_code = response.status_code if response else "N/A"
            error_text = response.text if response else "No response received"
            error_data = None
            if response:
                try:
                    error_data = response.json()
                except Exception:
                    pass  # Not JSON, use text instead

            logger.error(
                f"Failed to create calendar event: run_id={run.id}, "
                f"calendar_id={self.calendar_id}, status_code={status_code}, "
                f"error_data={error_data}, response_text={error_text[:500]}"
            )
            return None

    def create_lift_event(self, lift: Lift) -> Optional[str]:
        """Create a calendar event for a weightlifting workout.

        Args:
            lift: The Lift object to create an event for.

        Returns:
            Google Calendar event ID if successful, None otherwise.
        """
        event_title = f"Lift: {lift.title}"

        # Ensure timezone-aware datetimes
        start_dt = lift.start_time
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = lift.end_time
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        event_data = {
            "summary": event_title,
            "description": f"Workout synced from fitness app\nLift ID: {lift.id}",
            "start": {
                "dateTime": start_dt.isoformat(),
            },
            "end": {
                "dateTime": end_dt.isoformat(),
            },
        }

        url = f"{self.base_url}/calendars/{self.calendar_id}/events"
        response = self._make_request("POST", url, json=event_data)

        if response and 200 <= response.status_code < 300:
            event = response.json()
            event_id = event.get("id")
            logger.info(
                f"Successfully created calendar event: lift_id={lift.id}, "
                f"event_id={event_id}, calendar_id={self.calendar_id}"
            )
            return event_id
        else:
            status_code = response.status_code if response else "N/A"
            error_text = response.text if response else "No response received"
            error_data = None
            if response:
                try:
                    error_data = response.json()
                except Exception:
                    pass

            logger.error(
                f"Failed to create calendar event: lift_id={lift.id}, "
                f"calendar_id={self.calendar_id}, status_code={status_code}, "
                f"error_data={error_data}, response_text={error_text[:500]}"
            )
            return None

    def delete_workout_event(self, event_id: str) -> bool:
        """Delete a calendar event.

        Args:
            event_id: Google Calendar event ID to delete.

        Returns:
            True if successful, False otherwise.
        """
        url = f"{self.base_url}/calendars/{self.calendar_id}/events/{event_id}"
        response = self._make_request("DELETE", url)

        if response and response.status_code == 204:
            logger.info(
                f"Successfully deleted calendar event: event_id={event_id}, "
                f"calendar_id={self.calendar_id}"
            )
            return True
        else:
            status_code = response.status_code if response else "N/A"
            error_text = response.text if response else "No response received"
            error_data = None
            if response:
                try:
                    error_data = response.json()
                except Exception:
                    pass  # Not JSON, use text instead

            logger.error(
                f"Failed to delete calendar event: event_id={event_id}, "
                f"calendar_id={self.calendar_id}, status_code={status_code}, "
                f"error_data={error_data}, response_text={error_text[:500]}"
            )
            return False

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a calendar event by ID.

        Args:
            event_id: Google Calendar event ID.

        Returns:
            Event data dict if successful, None otherwise.
        """
        url = f"{self.base_url}/calendars/{self.calendar_id}/events/{event_id}"
        response = self._make_request("GET", url)

        if response and response.status_code == 200:
            logger.info(
                f"Successfully retrieved calendar event: event_id={event_id}, "
                f"calendar_id={self.calendar_id}"
            )
            return response.json()
        else:
            status_code = response.status_code if response else "N/A"
            error_text = response.text if response else "No response received"
            error_data = None
            if response:
                try:
                    error_data = response.json()
                except Exception:
                    pass  # Not JSON, use text instead

            logger.error(
                f"Failed to get calendar event: event_id={event_id}, "
                f"calendar_id={self.calendar_id}, status_code={status_code}, "
                f"error_data={error_data}, response_text={error_text[:500]}"
            )
            return None
