"""
Integration Layer — Google Calendar (Read-Only, Phase 1)
Reads upcoming events from Google Calendar and syncs them into
the local SQLite store. No writes in Phase 1.

Requirements:
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Setup (one-time):
  1. Go to https://console.cloud.google.com/
  2. Create a project → enable "Google Calendar API".
  3. Create OAuth 2.0 credentials (Desktop app) → download as JSON.
  4. Save the JSON to the path set in config/settings.yaml
     → integrations.google_calendar.credentials_file
  5. Run `python main.py --setup-gcal` the first time to complete the
     OAuth browser flow. A token file is saved automatically for future runs.
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Phase 1 scope: read-only
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GCalReader:
    """
    Read-only Google Calendar connector.
    Fetches events and syncs them to the local SQLite store.
    """

    def __init__(self, credentials_file: str, token_file: str, calendars: list[str]):
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.calendars = calendars or ["primary"]
        self._service = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def authenticate(self) -> None:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds: Optional[Credentials] = None

        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("GCal token refreshed.")
            else:
                if not self.credentials_file.exists():
                    raise FileNotFoundError(
                        f"Google credentials file not found: {self.credentials_file}\n"
                        "Download it from Google Cloud Console and update settings.yaml."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file), SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("GCal OAuth flow completed.")

            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(creds.to_json())

        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        http = httplib2.Http(disable_ssl_certificate_validation=True)
        authorized_http = AuthorizedHttp(creds, http=http)
        self._service = build("calendar", "v3", http=authorized_http)
        logger.info("Google Calendar service ready.")

    def __enter__(self):
        self.authenticate()
        return self

    def __exit__(self, *_):
        pass

    # ── Fetch events ──────────────────────────────────────────────────────────

    def fetch_upcoming_events(
        self, days_ahead: int = 14, max_results: int = 50
    ) -> list[dict]:
        if not self._service:
            raise RuntimeError("Call authenticate() first.")

        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()

        all_events = []
        for cal_id in self.calendars:
            try:
                result = (
                    self._service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=max_results,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
            except Exception as exc:
                logger.error("GCal fetch error for calendar '%s': %s", cal_id, exc)
                continue

            for item in result.get("items", []):
                all_events.append(self._normalise_event(item, cal_id))

        logger.info("Fetched %d calendar events.", len(all_events))
        return all_events

    @staticmethod
    def _normalise_event(item: dict, calendar_id: str) -> dict:
        start = item.get("start", {})
        end = item.get("end", {})

        start_time = start.get("dateTime") or start.get("date", "")
        end_time = end.get("dateTime") or end.get("date", "")

        attendees = json.dumps(
            [a.get("email", "") for a in item.get("attendees", [])]
        )

        return {
            "gcal_event_id": item.get("id", ""),
            "title":         item.get("summary", "(No title)"),
            "start_time":    start_time,
            "end_time":      end_time,
            "attendees":     attendees,
            "description":   item.get("description", ""),
            "location":      item.get("location", ""),
            "calendar_id":   calendar_id,
        }

    # ── Sync helper ───────────────────────────────────────────────────────────

    def sync_events_to_sqlite(self, sqlite_store, days_ahead: int = 14) -> int:
        if not self._service:
            self.authenticate()
        events = self.fetch_upcoming_events(days_ahead=days_ahead)
        for e in events:
            sqlite_store.upsert_event(
                gcal_event_id=e["gcal_event_id"],
                title=e["title"],
                start_time=e["start_time"],
                end_time=e["end_time"],
                attendees=e["attendees"],
                description=e["description"],
                location=e["location"],
                calendar_id=e["calendar_id"],
            )
        sqlite_store.log_interaction(
            source="gcal",
            event_type="event_sync",
            summary=f"Synced {len(events)} calendar events.",
            raw_json=json.dumps(events),
        )
        return len(events)

    # Keep old method name working
    def sync_to_sqlite(self, sqlite_store) -> int:
        return self.sync_events_to_sqlite(sqlite_store)


class GCalWriter:
    """Write events to Google Calendar."""

    def __init__(self, token_file: str, credentials_file: str, calendar_id: str = "primary"):
        self.token_file = Path(token_file)
        self.credentials_file = Path(credentials_file)
        self.calendar_id = calendar_id
        self._service = None

    def authenticate(self, creds=None) -> None:
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        from googleapiclient.discovery import build

        if creds is None:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials.from_authorized_user_file(str(self.token_file))
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        http = httplib2.Http(disable_ssl_certificate_validation=True)
        authorized_http = AuthorizedHttp(creds, http=http)
        self._service = build("calendar", "v3", http=authorized_http)
        logger.info("GCalWriter service ready.")

    def _get_service(self):
        if self._service is None:
            self.authenticate()
        return self._service

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: list = None,
        all_day: bool = False,
    ) -> str:
        """
        Create a new calendar event. Returns the new event ID.

        Args:
            start_time: ISO 8601 datetime string (e.g. '2026-04-10T14:00:00+05:30')
                        or date string for all-day events (e.g. '2026-04-10')
            end_time:   Same format as start_time.
            all_day:    If True, treats start/end as date strings (no time).
        """
        service = self._get_service()

        if all_day:
            start = {"date": start_time[:10]}
            end = {"date": end_time[:10]}
        else:
            start = {"dateTime": start_time, "timeZone": "UTC"}
            end = {"dateTime": end_time, "timeZone": "UTC"}

        body = {
            "summary": title,
            "start": start,
            "end": end,
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        result = service.events().insert(calendarId=self.calendar_id, body=body).execute()
        event_id = result.get("id", "")
        logger.info("Created GCal event '%s' (%s)", title, event_id)
        return event_id

    def update_event(
        self,
        event_id: str,
        title: str = "",
        start_time: str = "",
        end_time: str = "",
        description: str = "",
        location: str = "",
        attendees: list = None,
    ) -> None:
        """Update an existing calendar event by event ID."""
        service = self._get_service()

        # Fetch current event to merge changes
        event = service.events().get(calendarId=self.calendar_id, eventId=event_id).execute()

        if title:
            event["summary"] = title
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if start_time:
            if "dateTime" in event.get("start", {}):
                event["start"] = {"dateTime": start_time, "timeZone": "UTC"}
            else:
                event["start"] = {"date": start_time[:10]}
        if end_time:
            if "dateTime" in event.get("end", {}):
                event["end"] = {"dateTime": end_time, "timeZone": "UTC"}
            else:
                event["end"] = {"date": end_time[:10]}
        if attendees is not None:
            event["attendees"] = [{"email": a} for a in attendees]

        service.events().update(
            calendarId=self.calendar_id, eventId=event_id, body=event
        ).execute()
        logger.info("Updated GCal event %s", event_id)

    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event by event ID. Requires manual confirmation. Returns True if deleted."""
        confirm = input(f"Permanently delete calendar event '{event_id}'? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Deletion cancelled.")
            return False
        service = self._get_service()
        service.events().delete(calendarId=self.calendar_id, eventId=event_id).execute()
        logger.info("Deleted GCal event %s", event_id)
        return True
