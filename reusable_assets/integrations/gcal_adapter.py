"""
Google Calendar adapter — wraps GCalReader + GCalWriter behind DataSourceAdapter.

Supports pull for: calendar events.
Supports push for: event (create).
"""

import logging
from pathlib import Path
import yaml
from integrations.base import DataSourceAdapter
from integrations.gcal_client import GCalReader, GCalWriter

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_settings() -> dict:
    with open(_SETTINGS_PATH, "r") as f:
        return yaml.safe_load(f)


class GCalAdapter(DataSourceAdapter):
    """
    Pluggable adapter for Google Calendar.

    When instantiated with no arguments (e.g. via AdapterRegistry), loads
    settings from config/settings.yaml automatically.
    """

    source_name = "google_calendar"

    def __init__(self, settings: dict = None, creds=None, days_ahead: int = 14):
        if settings is None:
            settings = _load_settings()
        google_cfg = settings["integrations"]["google"]
        gcal_cfg   = settings["integrations"]["google_calendar"]

        self._reader = GCalReader(
            credentials_file=google_cfg["credentials_file"],
            token_file=google_cfg["token_file"],
            calendars=gcal_cfg.get("calendars", ["primary"]),
        )
        self._writer = GCalWriter(
            token_file=google_cfg["token_file"],
            credentials_file=google_cfg["credentials_file"],
        )
        self._days_ahead = days_ahead

        if creds is not None:
            # Inject pre-built credentials so OAuth is not re-run
            from googleapiclient.discovery import build
            self._reader._service = build("calendar", "v3", credentials=creds)
            self._writer.authenticate(creds=creds)

    # ── DataSourceAdapter contract ─────────────────────────────────────────────

    def pull(self, sqlite_store) -> int:
        """Sync upcoming calendar events from Google Calendar into SQLite."""
        return self._reader.sync_events_to_sqlite(
            sqlite_store, days_ahead=self._days_ahead
        )

    def push(self, entity_type: str, data: dict) -> str:
        """
        Create a calendar event in Google Calendar. Returns the gcal event ID.

        Supported entity_types: "event".
        """
        if entity_type == "event":
            return self._writer.create_event(**data)
        raise NotImplementedError(
            f"GCalAdapter does not support push for entity_type='{entity_type}'"
        )

    def schema_map(self) -> dict:
        return {
            "event": {
                "title":       "summary",
                "start_time":  "start.dateTime",
                "end_time":    "end.dateTime",
                "description": "description",
                "location":    "location",
                "attendees":   "attendees[].email",
            },
        }
