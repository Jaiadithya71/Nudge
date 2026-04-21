"""
ingestion_service.py - Syncs external data into Memory.

Active sources:
  - Google Calendar (events)
  - Google People API (contacts)

Tasks and goals are managed exclusively via the dashboard (SQLite).
Notion connectors are archived in input/connectors/_archived/.
"""

import logging
from typing import Any

from .connectors.calendar_connector import CalendarConnector
from .connectors.google_contacts_connector import GoogleContactsConnector
from .normalizers.calendar_normalizer import normalize_events
from .normalizers.contact_normalizer import normalize_contacts

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, memory_module: Any):
        self.memory = memory_module

    def ingest_all(self, user_id: str) -> None:
        """Fetch Google Calendar events and Google contacts, persist to memory."""
        self._ingest_events(user_id)
        self._ingest_contacts(user_id)

    def _ingest_events(self, user_id: str) -> None:
        try:
            raw = CalendarConnector().fetch_events(user_id)
            for e in normalize_events(raw):
                self.memory.ingest("events", e, user_id)
            logger.info("Ingested %d event(s) for user=%s", len(raw), user_id)
        except Exception as exc:
            logger.warning("Calendar ingestion failed for user=%s: %s", user_id, exc)

    def _ingest_contacts(self, user_id: str) -> None:
        try:
            raw = GoogleContactsConnector().fetch_contacts(user_id)
            for c in normalize_contacts(raw):
                self.memory.ingest("contacts", c, user_id)
            logger.info("Ingested %d contact(s) for user=%s", len(raw), user_id)
        except Exception as exc:
            logger.warning("Contacts ingestion failed for user=%s: %s", user_id, exc)
