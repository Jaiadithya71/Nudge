"""
Pluggable adapter contract for all data source integrations.

To add a new platform (FHIR, insurance, LinkedIn, etc.):
  1. Create a new file in integrations/ (or integrations/adapters/ for third-party).
  2. Subclass DataSourceAdapter and implement the three abstract methods.
  3. Register the adapter in main.py (or the FastAPI server's startup).
  4. MemoryEngine.sync_all(adapters=[...]) handles the rest — no engine changes.

This pattern means the memory core never needs to know about specific platforms.
"""

from abc import ABC, abstractmethod
from typing import Optional


class DataSourceAdapter(ABC):
    """
    Abstract base for all data source integrations.

    Responsibilities:
      - pull()      : read from the external source → write into SQLiteStore
      - push()      : write a canonical entity → the external source
      - schema_map(): declare how canonical fields map to this source's field names
                      (used by the export / consent layer to translate data)

    One adapter = one external platform. Adding a platform is one file, no core changes.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        Unique slug for this data source.
        Must match the 'source' value stored in external_refs.
        e.g. "google_contacts" | "google_calendar" | "notion" | "fhir" | "insurance"
        """

    @abstractmethod
    def pull(self, sqlite_store) -> int:
        """
        Pull all data from the external source and write it into sqlite_store.

        The sqlite_store already carries the correct user_id — no need to pass it
        separately. All writes are automatically scoped to that user.

        Returns the number of records synced (for reporting).
        """

    @abstractmethod
    def push(self, entity_type: str, data: dict) -> str:
        """
        Push a single canonical entity to the external source.

        Args:
            entity_type : "contact" | "task" | "goal" | "event"
            data        : canonical field dict (keys match the core model field names)

        Returns the external_id assigned by the source (stored in external_refs).
        Raises NotImplementedError for entity types this adapter does not support.
        """

    def schema_map(self) -> dict:
        """
        Optional: map canonical field names → this source's field names, per entity type.

        Used by the export / consent layer to translate data into the target platform's
        format without embedding platform logic in the core.

        Example:
            {
                "contact": {"name": "displayName", "email": "emailAddresses[0].value"},
                "event":   {"title": "summary", "start_time": "start.dateTime"},
            }

        Return empty dict (default) if the source uses canonical names directly.
        """
        return {}

    @property
    def schema_version(self) -> str:
        """
        Semantic version of this adapter's field-mapping contract.
        Bump when schema_map() changes in a breaking way so importers can detect
        incompatible bundles at import time.
        """
        return "1.0"

    @property
    def description(self) -> str:
        """Human-readable summary of what this adapter syncs. Used by the registry."""
        return ""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source='{self.source_name}' v{self.schema_version}>"
