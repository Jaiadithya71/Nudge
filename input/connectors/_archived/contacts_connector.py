"""
contacts_connector.py - Fetches contacts from the Notion Contacts database.

Property mapping (from live schema):
    Name          → name (title)
    Email         → email (email)
    Phone         → phone (phone_number)
    Role          → role (rich_text)
    Organisation  → organisation (rich_text)
    Last Contact  → last_interaction (date)
    Relationship  → importance scoring (select: Close Friend / Friend / Acquaintance / New / etc.)
"""

import os
import logging
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

from input.config import get

logger = logging.getLogger(__name__)

# Map Relationship select → importance_score (0.0–1.0)
_RELATIONSHIP_SCORE: dict[str, float] = {
    "close friend": 1.0,
    "close":        1.0,
    "friend":       0.8,
    "colleague":    0.6,
    "acquaintance": 0.4,
    "new":          0.2,
}


def _rich_text(prop: dict) -> str:
    parts = prop.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in parts)


class ContactsConnector:
    def __init__(self):
        load_dotenv()
        self.api_key     = os.environ.get("NOTION_API_KEY", "")
        self.database_id = get("integrations.notion.databases.contacts",
                               "335cefe4ebef8184a1c0e8f5c349fb9f")
        self.base_url    = "https://api.notion.com/v1"
        self.headers     = {
            "Authorization":  f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type":   "application/json",
        }

    def fetch_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("NOTION_API_KEY not set — skipping contacts fetch.")
            return []

        logger.info("Fetching Notion contacts from database %s", self.database_id)
        try:
            response = requests.post(
                f"{self.base_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json={"page_size": 100},
                timeout=8,
            )
            response.raise_for_status()

            contacts = []
            for page in response.json().get("results", []):
                props = page.get("properties", {})

                title_parts = props.get("Name", {}).get("title", [])
                name = "".join(t.get("plain_text", "") for t in title_parts) or "Unknown"

                email            = props.get("Email", {}).get("email") or ""
                last_contact_obj = props.get("Last Contact", {}).get("date") or {}
                last_interaction = last_contact_obj.get("start")

                relationship_obj = props.get("Relationship", {}).get("select") or {}
                relationship_raw = (relationship_obj.get("name") or "").lower()
                importance_score = 0.3  # default
                for key, score in _RELATIONSHIP_SCORE.items():
                    if key in relationship_raw:
                        importance_score = score
                        break

                contacts.append({
                    "contact_id":       page.get("id"),
                    "name":             name,
                    "email":            email,
                    "last_interaction": last_interaction,
                    "importance_score": importance_score,
                })

            return contacts

        except Exception as exc:
            logger.error("Failed to fetch Notion contacts: %s", exc)
            return []
