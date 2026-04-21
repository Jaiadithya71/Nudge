"""
calendar_connector.py - Fetches live data from Google Calendar API.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from input.config import get, project_root

logger = logging.getLogger(__name__)

_ROOT = project_root()


def _ensure_datetime(dt_str: str) -> str:
    """Normalise all-day date strings (YYYY-MM-DD) to ISO datetime (midnight UTC)."""
    if dt_str and "T" not in dt_str:
        return dt_str + "T00:00:00Z"
    return dt_str


class CalendarConnector:
    def __init__(self):
        token_file  = get("integrations.google.token_file",       "gcal_token.json")
        self.token_file  = _ROOT / token_file
        self.scopes = get("integrations.google.scopes",
                          ["https://www.googleapis.com/auth/calendar"])

    def _get_credentials(self) -> Credentials | None:
        if not self.token_file.exists():
            logger.warning("Google Calendar token missing at %s. Skipping.", self.token_file)
            return None

        creds = Credentials.from_authorized_user_file(str(self.token_file), self.scopes)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("Google Calendar token expired — refreshing...")
                try:
                    creds.refresh(Request())
                    # Persist the refreshed token so we don't refresh every time
                    with open(self.token_file, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                    logger.info("Token refreshed and saved.")
                except Exception as exc:
                    logger.error("Token refresh failed: %s", exc)
                    return None
            else:
                logger.warning("Google Calendar credentials invalid and cannot be refreshed.")
                return None

        return creds

    def fetch_events(self, user_id: str) -> List[Dict[str, Any]]:
        creds = self._get_credentials()
        if creds is None:
            return []

        try:
            service = build("calendar", "v3", credentials=creds)

            now = datetime.now(timezone.utc)
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            time_max = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

            calendars = get("integrations.google_calendar.calendars", ["primary"])
            events: List[Dict[str, Any]] = []

            for cal_id in calendars:
                logger.info("Fetching Google Calendar events from '%s' (%s → %s)",
                            cal_id, time_min, time_max)
                result = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()

                for row in result.get("items", []):
                    start = _ensure_datetime(row["start"].get("dateTime", row["start"].get("date", "")))
                    end   = _ensure_datetime(row["end"].get("dateTime",   row["end"].get("date", "")))
                    events.append({
                        "id":           row.get("id"),
                        "title":        row.get("summary", "Untitled Event"),
                        "start":        start,
                        "end":          end,
                        "participants": [p.get("email") for p in row.get("attendees", [])],
                        "location":     row.get("location", ""),
                    })

            return events

        except HttpError as exc:
            logger.error("Google Calendar API error: %s", exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error fetching calendar events: %s", exc)
            return []
