"""
Google Contacts adapter — wraps GContactsReader + GContactsWriter behind DataSourceAdapter.

Supports pull for: contacts (base layer).
Supports push for: contact (create/update).
"""

import logging
from pathlib import Path
import yaml
from integrations.base import DataSourceAdapter
from integrations.gcontacts_client import GContactsReader, GContactsWriter

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def _load_settings() -> dict:
    with open(_SETTINGS_PATH, "r") as f:
        return yaml.safe_load(f)


class GContactsAdapter(DataSourceAdapter):
    """
    Pluggable adapter for Google Contacts (People API).

    When instantiated with no arguments (e.g. via AdapterRegistry), loads
    settings from config/settings.yaml automatically.
    """

    source_name = "google_contacts"

    def __init__(self, settings: dict = None, creds=None):
        if settings is None:
            settings = _load_settings()
        google_cfg = settings["integrations"]["google"]

        self._reader = GContactsReader(
            token_file=google_cfg["token_file"],
            credentials_file=google_cfg["credentials_file"],
        )
        self._writer = GContactsWriter(
            token_file=google_cfg["token_file"],
            credentials_file=google_cfg["credentials_file"],
        )

        if creds is not None:
            self._reader.authenticate(creds=creds)
            self._writer.authenticate(creds=creds)

    # ── DataSourceAdapter contract ─────────────────────────────────────────────

    def pull(self, sqlite_store) -> int:
        """Sync all Google Contacts into SQLite as the base contact layer."""
        return self._reader.sync_to_sqlite(sqlite_store)

    def push(self, entity_type: str, data: dict) -> str:
        """
        Create or update a contact in Google Contacts.

        Supported entity_types: "contact".
        Returns the Google resource name (e.g. "people/c1234567890").
        """
        if entity_type == "contact":
            if "resource_name" in data:
                # Update existing contact
                resource_name = data.pop("resource_name")
                self._writer.update_contact(resource_name=resource_name, **data)
                return resource_name
            return self._writer.create_contact(**data)
        raise NotImplementedError(
            f"GContactsAdapter does not support push for entity_type='{entity_type}'"
        )

    def schema_map(self) -> dict:
        return {
            "contact": {
                "name":         "names[0].displayName",
                "email":        "emailAddresses[0].value",
                "phone":        "phoneNumbers[0].value",
                "organisation": "organizations[0].name",
                "role":         "organizations[0].title",
                "notes":        "biographies[0].value",
                "linkedin_url": "urls[type=linkedin].value",
            },
        }
