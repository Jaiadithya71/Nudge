from .base import DataSourceAdapter
from .notion_client import NotionReader, NotionWriter
from .gcal_client import GCalReader, GCalWriter
from .gcontacts_client import GContactsReader, GContactsWriter
from .notion_adapter import NotionAdapter
from .gcal_adapter import GCalAdapter
from .gcontacts_adapter import GContactsAdapter

__all__ = [
    # Base contract
    "DataSourceAdapter",
    # Raw clients (kept for direct use / testing)
    "NotionReader", "NotionWriter",
    "GCalReader", "GCalWriter",
    "GContactsReader", "GContactsWriter",
    # Adapters (preferred for sync_all)
    "NotionAdapter", "GCalAdapter", "GContactsAdapter",
]
