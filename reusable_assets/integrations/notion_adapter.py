"""
Notion adapter — wraps NotionReader + NotionWriter behind the DataSourceAdapter contract.

Supports pull for: contacts, tasks, goals, discussions.
Supports push for: contact, task, goal.
"""

import logging
import os
from pathlib import Path
import yaml
from integrations.base import DataSourceAdapter
from integrations.notion_client import NotionReader, NotionWriter

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_settings() -> dict:
    with open(_SETTINGS_PATH, "r") as f:
        return yaml.safe_load(f)


class NotionAdapter(DataSourceAdapter):
    """
    Pluggable adapter for Notion.

    When instantiated with no arguments (e.g. via AdapterRegistry), loads
    api_key from the NOTION_API_KEY env var and settings from config/settings.yaml.
    """

    source_name = "notion"

    def __init__(self, api_key: str = None, settings: dict = None):
        if api_key is None:
            api_key = os.getenv("NOTION_API_KEY", "")
        if settings is None:
            settings = _load_settings()
        self._reader = NotionReader(api_key=api_key, settings=settings)
        self._writer = NotionWriter(api_key=api_key, settings=settings)

    # ── DataSourceAdapter contract ─────────────────────────────────────────────

    def pull(self, sqlite_store) -> int:
        """Sync goals, tasks, contacts (+ discussions) from Notion into SQLite."""
        return self._reader.sync_to_sqlite(sqlite_store)

    def push(self, entity_type: str, data: dict) -> str:
        """
        Create an entity in Notion and return the new Notion page ID.

        Supported entity_types: "contact", "task", "goal".
        """
        if entity_type == "contact":
            return self._writer.create_contact(**data)
        if entity_type == "task":
            return self._writer.create_task(**data)
        if entity_type == "goal":
            return self._writer.create_goal(**data)
        raise NotImplementedError(
            f"NotionAdapter does not support push for entity_type='{entity_type}'"
        )

    def schema_map(self) -> dict:
        return {
            "contact": {
                "name":               "Name",
                "email":              "Email",
                "phone":              "Phone",
                "organisation":       "Organisation",
                "role":               "Role",
                "tags":               "Tags",
                "how_we_met":         "How We Met",
                "relationship_score": "Relationship",
                "last_contact_date":  "Last Contact",
                "next_followup_date": "Next Follow-up",
                "linkedin_url":       "LinkedIn",
                "notes":              "Notes",
            },
            "task": {
                "title":    "Name",
                "status":   "Status",
                "priority": "Priority",
                "due_date": "Due",
            },
            "goal": {
                "title":       "Name",
                "status":      "Status",
                "deadline":    "Deadline",
                "description": "Notes",
            },
        }
