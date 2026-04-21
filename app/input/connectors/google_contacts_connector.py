"""
google_contacts_connector.py — Fetches contacts from Google People API.

Uses the same OAuth token as the calendar connector (gcal_token.json).
The token must have been authorized with the contacts scope:
    https://www.googleapis.com/auth/contacts

People API field mapping → internal schema:
    resourceName          → contact_id  (e.g. "people/c12345")
    names[0].displayName  → name
    emailAddresses[0]     → email
    metadata.sources[0].updateTime → last_interaction (ISO timestamp)
    biographies / labels  → importance_score heuristic
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from input.config import get, project_root

logger = logging.getLogger(__name__)

_ROOT = project_root()

# Fields to request from the People API
_PERSON_FIELDS = ",".join([
    "names",
    "emailAddresses",
    "metadata",
    "biographies",
    "userDefined",
])


def _importance_from_contact(person: dict) -> float:
    """
    Heuristic importance score (0.0–1.0) derived from available People API fields.

    - Has email + biography (personal note) → 0.8
    - Has email only                        → 0.6
    - No email                              → 0.3
    - userDefined label "close" / "vip"     → bumped to 1.0
    """
    score = 0.3

    if person.get("emailAddresses"):
        score = 0.6

    if person.get("biographies"):
        score = 0.8

    # Check userDefined fields for a relationship label
    for field in person.get("userDefined", []):
        key = (field.get("key") or "").lower()
        val = (field.get("value") or "").lower()
        if key in ("relationship", "label") or val in ("close", "vip", "close friend", "friend"):
            if val in ("close", "vip", "close friend"):
                score = 1.0
            elif val in ("friend",):
                score = max(score, 0.8)
            elif val in ("colleague", "work"):
                score = max(score, 0.6)

    return score


class GoogleContactsConnector:
    def __init__(self):
        token_file = get("integrations.google.token_file", "gcal_token.json")
        self.token_file = _ROOT / token_file
        self.scopes = get("integrations.google.scopes", [
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/contacts",
        ])

    def _get_credentials(self) -> Credentials | None:
        if not self.token_file.exists():
            logger.warning("Google token missing at %s — skipping contacts fetch.", self.token_file)
            return None

        creds = Credentials.from_authorized_user_file(str(self.token_file), self.scopes)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(self.token_file, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                    logger.info("Google token refreshed.")
                except Exception as exc:
                    logger.error("Token refresh failed: %s", exc)
                    return None
            else:
                logger.warning("Google credentials invalid and cannot be refreshed.")
                return None

        return creds

    def fetch_contacts(self, user_id: str) -> List[Dict[str, Any]]:
        creds = self._get_credentials()
        if creds is None:
            return []

        try:
            service = build("people", "v1", credentials=creds)

            contacts = []
            page_token = None

            while True:
                kwargs: dict = {
                    "resourceName": "people/me",
                    "pageSize": 100,
                    "personFields": _PERSON_FIELDS,
                }
                if page_token:
                    kwargs["pageToken"] = page_token

                result = service.people().connections().list(**kwargs).execute()

                for person in result.get("connections", []):
                    resource_name = person.get("resourceName", "")

                    names = person.get("names", [])
                    name = names[0].get("displayName", "Unknown") if names else "Unknown"

                    emails = person.get("emailAddresses", [])
                    email = emails[0].get("value", "") if emails else ""

                    # Use the most recent source update time as a proxy for last interaction
                    last_interaction = None
                    sources = person.get("metadata", {}).get("sources", [])
                    if sources:
                        # sources are ordered most-recently-updated first
                        last_interaction = sources[0].get("updateTime")
                        # Trim to ISO date only (YYYY-MM-DD)
                        if last_interaction and "T" in last_interaction:
                            last_interaction = last_interaction[:10]

                    contacts.append({
                        "contact_id":       resource_name,
                        "name":             name,
                        "email":            email,
                        "last_interaction": last_interaction,
                        "importance_score": _importance_from_contact(person),
                    })

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            logger.info("Fetched %d contact(s) from Google People API for user=%s",
                        len(contacts), user_id)
            return contacts

        except HttpError as exc:
            logger.error("Google People API error: %s", exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error fetching contacts: %s", exc)
            return []
