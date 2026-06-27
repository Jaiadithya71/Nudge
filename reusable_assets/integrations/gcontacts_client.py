"""
Integration Layer — Google Contacts via People API (Read-Only, Phase 1)
Imports all contacts from your Google/Android account into SQLite.

This becomes the BASE LAYER of your social graph.
Notion CRM enriches the important subset; everyone else lives here.

Scope required (added alongside calendar.readonly):
  https://www.googleapis.com/auth/contacts.readonly

The People API returns rich data per contact:
  names, emailAddresses, phoneNumbers, organizations, biographies, urls
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CONTACTS_SCOPE = "https://www.googleapis.com/auth/contacts.readonly"


class GContactsReader:
    """
    Read-only Google Contacts connector using the People API.
    Auth is shared with GCalReader — both scopes are requested together.
    """

    def __init__(self, token_file: str, credentials_file: str):
        self.token_file       = token_file
        self.credentials_file = credentials_file
        self._service         = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def authenticate(self, creds=None) -> None:
        """
        Accepts a pre-built Credentials object (shared with GCalReader)
        or builds one from the token file.
        """
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        from googleapiclient.discovery import build

        if creds is None:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from pathlib import Path

            p = Path(self.token_file)
            if not p.exists():
                raise FileNotFoundError(
                    f"Token file not found: {self.token_file}\n"
                    "Run: python main.py --setup-google"
                )
            creds = Credentials.from_authorized_user_file(str(p), [CONTACTS_SCOPE])
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        http = httplib2.Http(disable_ssl_certificate_validation=True)
        authorized_http = AuthorizedHttp(creds, http=http)
        self._service = build("people", "v1", http=authorized_http)
        logger.info("Google Contacts (People API) service ready.")

    def __enter__(self):
        self.authenticate()
        return self

    def __exit__(self, *_):
        pass

    # ── Fetch all contacts ────────────────────────────────────────────────────

    def fetch_all_contacts(self, sync_token: str = "") -> tuple[list[dict], str]:
        """
        Fetch contacts from Google Contacts.

        If sync_token is provided, only changed contacts since that token are
        returned (incremental sync). Otherwise a full fetch is performed.

        Returns (contacts, new_sync_token).
        """
        if not self._service:
            raise RuntimeError("Call authenticate() first.")

        all_contacts = []
        page_token   = None
        new_sync_token = ""

        while True:
            kwargs = {
                "resourceName": "people/me",
                "pageSize":     1000,
                "personFields": (
                    "names,emailAddresses,phoneNumbers,"
                    "organizations,biographies,urls,metadata"
                ),
                "requestSyncToken": True,
            }
            if sync_token and not page_token:
                # Incremental: only fetch changes since last sync
                kwargs["syncToken"] = sync_token
            if page_token:
                kwargs["pageToken"] = page_token

            try:
                resp = self._service.people().connections().list(**kwargs).execute()
            except Exception as exc:
                error_str = str(exc)
                if "Sync token" in error_str or "INVALID_SYNC_TOKEN" in error_str or "410" in error_str:
                    # Token expired (valid for 7 days) — fall back to full sync
                    logger.warning("Sync token expired, falling back to full sync.")
                    return self.fetch_all_contacts(sync_token="")
                logger.error("People API error: %s", exc)
                break

            for person in resp.get("connections", []):
                contact = self._normalise(person)
                if contact["name"]:
                    all_contacts.append(contact)

            new_sync_token = resp.get("nextSyncToken", new_sync_token)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        mode = "incremental" if sync_token else "full"
        logger.info("Fetched %d contacts from Google Contacts (%s sync).", len(all_contacts), mode)
        return all_contacts, new_sync_token

    # ── Normalise ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(person: dict) -> dict:
        resource_name = person.get("resourceName", "")

        names = person.get("names", [])
        name  = ""
        if names:
            name = names[0].get("displayName", "")
            if not name:
                given  = names[0].get("givenName", "")
                family = names[0].get("familyName", "")
                name   = f"{given} {family}".strip()

        emails = person.get("emailAddresses", [])
        email  = emails[0].get("value", "") if emails else ""

        phones = person.get("phoneNumbers", [])
        phone  = phones[0].get("value", "") if phones else ""

        orgs   = person.get("organizations", [])
        org    = orgs[0].get("name",  "") if orgs else ""
        role   = orgs[0].get("title", "") if orgs else ""

        bios  = person.get("biographies", [])
        notes = bios[0].get("value", "") if bios else ""

        linkedin = ""
        for url_entry in person.get("urls", []):
            url_type  = url_entry.get("type", "").lower()
            url_value = url_entry.get("value", "")
            if "linkedin" in url_type or "linkedin" in url_value.lower():
                linkedin = url_value
                break

        return {
            "google_resource_name": resource_name,
            "name":                 name,
            "email":                email,
            "phone":                phone,
            "organisation":         org,
            "role":                 role,
            "notes":                notes,
            "linkedin_url":         linkedin,
        }

    # ── Sync helper ───────────────────────────────────────────────────────────

    def sync_to_sqlite(self, sqlite_store) -> int:
        if not self._service:
            self.authenticate()

        # Load stored sync token for incremental fetch
        token_row = sqlite_store.get_kv("gcontacts_sync_token")
        sync_token = token_row if token_row else ""

        contacts, new_sync_token = self.fetch_all_contacts(sync_token=sync_token)

        # Write all contacts in a single transaction — ~10x faster than per-row commits
        sqlite_store.begin_batch()
        try:
            for c in contacts:
                sqlite_store.upsert_google_contact(
                    google_resource_name=c["google_resource_name"],
                    name=c["name"],
                    email=c["email"],
                    phone=c["phone"],
                    organisation=c["organisation"],
                    role=c["role"],
                    notes=c["notes"],
                    linkedin_url=c["linkedin_url"],
                )
        finally:
            sqlite_store.end_batch()

        # Store the new sync token for next incremental run
        if new_sync_token:
            sqlite_store.set_kv("gcontacts_sync_token", new_sync_token)

        sqlite_store.log_interaction(
            source="google_contacts",
            event_type="contacts_sync",
            summary=f"Synced {len(contacts)} contacts from Google.",
            raw_json=json.dumps({"count": len(contacts), "incremental": bool(sync_token)}),
        )
        return len(contacts)


class GContactsWriter:
    """Write contacts to Google Contacts via the People API."""

    def __init__(self, token_file: str, credentials_file: str):
        self.token_file = token_file
        self.credentials_file = credentials_file
        self._service = None

    def authenticate(self, creds=None) -> None:
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        from googleapiclient.discovery import build

        if creds is None:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from pathlib import Path

            p = Path(self.token_file)
            creds = Credentials.from_authorized_user_file(str(p))
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        http = httplib2.Http(disable_ssl_certificate_validation=True)
        authorized_http = AuthorizedHttp(creds, http=http)
        self._service = build("people", "v1", http=authorized_http)
        logger.info("GContactsWriter (People API) service ready.")

    def _get_service(self):
        if self._service is None:
            self.authenticate()
        return self._service

    def create_contact(
        self,
        name: str,
        email: str = "",
        phone: str = "",
        organisation: str = "",
        role: str = "",
        notes: str = "",
    ) -> str:
        """Create a new Google Contact. Returns the resource name (e.g. 'people/c123')."""
        service = self._get_service()

        body = {
            "names": [{"displayName": name, "unstructuredName": name}],
        }
        if email:
            body["emailAddresses"] = [{"value": email}]
        if phone:
            body["phoneNumbers"] = [{"value": phone}]
        if organisation or role:
            body["organizations"] = [{"name": organisation, "title": role}]
        if notes:
            body["biographies"] = [{"value": notes, "contentType": "TEXT_PLAIN"}]

        result = service.people().createContact(body=body).execute()
        resource_name = result.get("resourceName", "")
        logger.info("Created Google Contact '%s' (%s)", name, resource_name)
        return resource_name

    def update_contact(
        self,
        resource_name: str,
        name: str = "",
        email: str = "",
        phone: str = "",
        organisation: str = "",
        role: str = "",
        notes: str = "",
    ) -> None:
        """Update an existing Google Contact by resource name."""
        service = self._get_service()

        # Fetch current etag — required for updates
        person = service.people().get(
            resourceName=resource_name,
            personFields="names,emailAddresses,phoneNumbers,organizations,biographies,metadata",
        ).execute()
        etag = person.get("etag", "")

        body = {"etag": etag, "resourceName": resource_name}
        update_fields = []

        if name:
            body["names"] = [{"displayName": name, "unstructuredName": name}]
            update_fields.append("names")
        if email:
            body["emailAddresses"] = [{"value": email}]
            update_fields.append("emailAddresses")
        if phone:
            body["phoneNumbers"] = [{"value": phone}]
            update_fields.append("phoneNumbers")
        if organisation or role:
            body["organizations"] = [{"name": organisation, "title": role}]
            update_fields.append("organizations")
        if notes:
            body["biographies"] = [{"value": notes, "contentType": "TEXT_PLAIN"}]
            update_fields.append("biographies")

        if not update_fields:
            logger.warning("update_contact called with no fields to update.")
            return

        service.people().updateContact(
            resourceName=resource_name,
            updatePersonFields=",".join(update_fields),
            body=body,
        ).execute()
        logger.info("Updated Google Contact %s", resource_name)

    # delete_contact intentionally not implemented — deletion permission is not granted.
