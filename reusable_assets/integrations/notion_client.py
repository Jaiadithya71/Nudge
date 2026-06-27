"""
Integration Layer — Notion (Read-Only, Phase 1)
Reads Tasks and Contacts from your Notion workspace and syncs them
into the local SQLite store. No writes in Phase 1.

Requirements:
  pip install notion-client

Setup:
  1. Go to https://www.notion.so/my-integrations and create a new integration.
  2. Copy the "Internal Integration Token" -> set as NOTION_API_KEY in .env
  3. Share each database with your integration (open DB -> Connections).
  4. Paste the database IDs into config/settings.yaml.

Contacts Database - expected Notion properties:
  Name              Title
  Email             Email
  Phone             Phone number
  Organisation      Text
  Role              Text              (job title)
  Tags              Multi-select      (vip, investor, family, colleague)
  How We Met        Text
  Relationship      Select            (Strong | Active | Dormant | New)
  Last Contact      Date
  Next Follow-up    Date
  LinkedIn          URL
  Notes             Text
  Discussions       (sub-pages or a linked Discussions DB)
"""

import json
import logging
from typing import Optional

from notion_client import Client as NotionSDK

logger = logging.getLogger(__name__)


# -- Property extractors -------------------------------------------------------

def _get_text(prop: dict) -> str:
    if not prop:
        return ""
    ptype = prop.get("type", "")
    if ptype == "title":
        parts = prop.get("title", [])
    elif ptype == "rich_text":
        parts = prop.get("rich_text", [])
    else:
        return ""
    return "".join(p.get("plain_text", "") for p in parts)


def _find_title(props: dict) -> str:
    """Find the title property regardless of what it's named."""
    for val in props.values():
        if val.get("type") == "title":
            return "".join(p.get("plain_text", "") for p in val.get("title", []))
    return ""


def _get_select(prop: dict) -> str:
    sel = (prop or {}).get("select") or {}
    return sel.get("name", "")


def _get_date(prop: dict) -> str:
    d = (prop or {}).get("date") or {}
    return d.get("start", "")


def _get_email(prop: dict) -> str:
    return (prop or {}).get("email", "") or ""


def _get_phone(prop: dict) -> str:
    return (prop or {}).get("phone_number", "") or ""


def _get_url(prop: dict) -> str:
    return (prop or {}).get("url", "") or ""


def _get_multi_select(prop: dict) -> str:
    """Return multi-select options as a comma-joined string."""
    options = (prop or {}).get("multi_select", [])
    return ",".join(opt.get("name", "") for opt in options)


# -- Reader --------------------------------------------------------------------

class NotionReader:
    """Read-only Notion connector."""

    def __init__(self, api_key: str, settings: dict):
        # Pin to 2022-06-28: notion-client v3 defaults to 2025-09-03 which
        # broke the databases/{id}/query endpoint.
        self._client = NotionSDK(auth=api_key, notion_version="2022-06-28")
        notion_cfg = settings.get("integrations", {}).get("notion", settings)
        self._db_ids: dict = notion_cfg.get("databases", settings.get("databases", {}))
        logger.info("NotionReader initialised.")

    # -- Pagination helper -----------------------------------------------------

    def _query_all(self, database_id: str, filter_obj: Optional[dict] = None) -> list:
        if not database_id:
            logger.warning("Notion database ID is empty -- skipping query.")
            return []

        pages, cursor = [], None
        while True:
            body: dict = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            if filter_obj:
                body["filter"] = filter_obj

            try:
                resp = self._client.request(
                    path=f"databases/{database_id}/query",
                    method="POST",
                    body=body,
                )
            except Exception as exc:
                logger.error("Notion API error: %s", exc)
                break

            pages.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

        return pages

    def _get_page_blocks(self, page_id: str) -> list:
        """Fetch all block children of a page."""
        try:
            resp = self._client.request(
                path=f"blocks/{page_id}/children",
                method="GET",
                query={"page_size": 100},
            )
            return resp.get("results", [])
        except Exception as exc:
            logger.error("Notion blocks fetch error for page %s: %s", page_id, exc)
            return []

    # -- Tasks -----------------------------------------------------------------

    def fetch_tasks(self) -> list[dict]:
        """
        Fetch all tasks from the Tasks database.

        Title property is detected dynamically (works with any column name).
        Status   -> status type
        Priority -> select type
        Due date -> date type (handles 'Due Date', 'Due date', 'Due')
        """
        db_id = self._db_ids.get("tasks", "")
        pages = self._query_all(db_id)
        tasks = []
        for page in pages:
            props = page.get("properties", {})
            tasks.append({
                "notion_page_id": page["id"],
                "title":          _find_title(props),
                "status":         _get_select(props.get("Status")),
                "priority":       _get_select(props.get("Priority")),
                "due_date":       _get_date(
                    props.get("Due Date") or props.get("Due date") or props.get("Due")
                ),
            })
        logger.info("Fetched %d tasks from Notion.", len(tasks))
        return tasks

    # -- Goals -----------------------------------------------------------------

    def fetch_goals(self) -> list[dict]:
        """
        Fetch all goals from the Goals Hub database.

        Title property is detected dynamically.
        Common properties handled:
          Status     -> select or status type  (Active | Completed | Paused)
          Deadline   -> date type              (also tries 'Due', 'Due Date')
          Priority   -> select type
          Notes      -> rich_text
        """
        db_id = self._db_ids.get("goals", "")
        pages = self._query_all(db_id)
        goals = []
        for page in pages:
            props = page.get("properties", {})

            # Status: handle both Notion 'status' type and plain 'select'
            status = ""
            for key in ["Status", "status", "State"]:
                if key in props:
                    p = props[key]
                    ptype = p.get("type", "")
                    if ptype == "status":
                        s = p.get("status") or {}
                        status = s.get("name", "")
                    elif ptype == "select":
                        s = p.get("select") or {}
                        status = s.get("name", "")
                    break

            deadline = _get_date(
                props.get("Deadline") or props.get("Due Date")
                or props.get("Due date") or props.get("Due")
            )
            description = _get_text(
                props.get("Notes") or props.get("Description") or props.get("About")
            )
            goals.append({
                "notion_page_id": page["id"],
                "title":          _find_title(props),
                "status":         status or "active",
                "deadline":       deadline,
                "description":    description,
            })
        logger.info("Fetched %d goals from Notion.", len(goals))
        return goals

    # -- Contacts --------------------------------------------------------------

    def fetch_contacts(self) -> list[dict]:
        """
        Fetch all contacts from the Contacts database (rich CRM schema).
        """
        db_id = self._db_ids.get("contacts", "")
        pages = self._query_all(db_id)
        contacts = []
        for page in pages:
            p = page.get("properties", {})
            contacts.append({
                "notion_page_id":     page["id"],
                "name":               _find_title(p),
                "email":              _get_email(p.get("Email")),
                "phone":              _get_phone(p.get("Phone")),
                "organisation":       _get_text(p.get("Organisation") or p.get("Company")),
                "role":               _get_text(p.get("Role") or p.get("Job Title")),
                "tags":               _get_multi_select(p.get("Tags")),
                "how_we_met":         _get_text(p.get("How We Met")),
                "relationship_score": _get_select(p.get("Relationship")),
                "last_contact_date":  _get_date(p.get("Last Contact")),
                "next_followup_date": _get_date(
                    p.get("Next Follow-up") or p.get("Next Followup")
                ),
                "linkedin_url":       _get_url(p.get("LinkedIn")),
                "notes":              _get_text(p.get("Notes")),
            })
        logger.info("Fetched %d contacts from Notion.", len(contacts))
        return contacts

    def fetch_discussions_for_page(self, page_id: str) -> list[dict]:
        """
        Read discussion notes from child pages or callout blocks titled with ISO dates.
        Returns list of dicts: {date, medium, summary, notion_block_id}
        """
        blocks = self._get_page_blocks(page_id)
        discussions = []

        for block in blocks:
            btype = block.get("type", "")

            if btype == "child_page":
                title = block.get("child_page", {}).get("title", "")
                date, medium = _parse_discussion_title(title)
                if date:
                    child_blocks = self._get_page_blocks(block["id"])
                    summary = _extract_text_from_blocks(child_blocks)
                    if summary:
                        discussions.append({
                            "discussion_date": date,
                            "medium":          medium,
                            "summary":         summary,
                            "notion_block_id": block["id"],
                        })

            elif btype == "callout":
                rich = block.get("callout", {}).get("rich_text", [])
                text = "".join(r.get("plain_text", "") for r in rich)
                date, medium = _parse_discussion_title(text[:30])
                if date and text:
                    discussions.append({
                        "discussion_date": date,
                        "medium":          medium,
                        "summary":         text,
                        "notion_block_id": block["id"],
                    })

        return discussions

    # -- Sync helpers ----------------------------------------------------------

    def sync_to_sqlite(self, sqlite_store) -> int:
        """Sync all Notion data (goals, tasks, contacts) into SQLite. Returns total rows."""
        total = 0
        total += self.sync_goals_to_sqlite(sqlite_store)
        total += self.sync_tasks_to_sqlite(sqlite_store)
        total += self.sync_contacts_to_sqlite(sqlite_store)
        return total

    def sync_goals_to_sqlite(self, sqlite_store) -> int:
        goals = self.fetch_goals()
        for g in goals:
            sqlite_store.upsert_goal(
                title=g["title"],
                status=g["status"],
                deadline=g["deadline"],
                description=g["description"],
                notion_page_id=g["notion_page_id"],
            )
        sqlite_store.log_interaction(
            source="notion",
            event_type="goal_sync",
            summary=f"Synced {len(goals)} goals.",
            raw_json=json.dumps(goals),
        )
        return len(goals)

    def sync_tasks_to_sqlite(self, sqlite_store) -> int:
        tasks = self.fetch_tasks()
        for t in tasks:
            sqlite_store.upsert_task(
                title=t["title"],
                status=t["status"],
                priority=t["priority"],
                due_date=t["due_date"],
                notion_page_id=t["notion_page_id"],
            )
        sqlite_store.log_interaction(
            source="notion",
            event_type="task_sync",
            summary=f"Synced {len(tasks)} tasks.",
            raw_json=json.dumps(tasks),
        )
        return len(tasks)

    def sync_contacts_to_sqlite(self, sqlite_store) -> int:
        """Sync contacts + their discussion history into SQLite."""
        contacts = self.fetch_contacts()
        for c in contacts:
            contact_id = sqlite_store.upsert_contact(
                name=c["name"],
                email=c["email"],
                phone=c["phone"],
                organisation=c["organisation"],
                role=c["role"],
                tags=c["tags"],
                how_we_met=c["how_we_met"],
                relationship_score=c["relationship_score"] or "New",
                last_contact_date=c["last_contact_date"],
                next_followup_date=c["next_followup_date"],
                linkedin_url=c["linkedin_url"],
                notes=c["notes"],
                notion_page_id=c["notion_page_id"],
            )

            discussions = self.fetch_discussions_for_page(c["notion_page_id"])
            for d in discussions:
                sqlite_store.add_discussion(
                    contact_id=contact_id,
                    discussion_date=d["discussion_date"],
                    medium=d["medium"],
                    summary=d["summary"],
                    notion_block_id=d["notion_block_id"],
                )

        sqlite_store.log_interaction(
            source="notion",
            event_type="contact_sync",
            summary=f"Synced {len(contacts)} contacts.",
            raw_json=json.dumps(contacts),
        )
        return len(contacts)


# -- Writer -------------------------------------------------------------------

class NotionWriter:
    """Write contacts, tasks, and goals back to Notion."""

    def __init__(self, api_key: str, settings: dict):
        self._client = NotionSDK(auth=api_key, notion_version="2022-06-28")
        notion_cfg = settings.get("integrations", {}).get("notion", settings)
        self._db_ids: dict = notion_cfg.get("databases", settings.get("databases", {}))
        logger.info("NotionWriter initialised.")

    def create_contact(
        self,
        name: str,
        email: str = "",
        phone: str = "",
        organisation: str = "",
        role: str = "",
        tags: list = None,
        how_we_met: str = "",
        relationship_score: str = "New",
        linkedin_url: str = "",
        notes: str = "",
    ) -> str:
        """Create a new contact page in the Notion Contacts DB. Returns the new page ID."""
        db_id = self._db_ids.get("contacts", "")
        if not db_id:
            raise ValueError("Notion contacts database ID not configured in settings.yaml")

        properties = {
            "Name": {"title": [{"text": {"content": name}}]},
        }
        if email:
            properties["Email"] = {"email": email}
        if phone:
            properties["Phone"] = {"phone_number": phone}
        if organisation:
            properties["Organisation"] = {"rich_text": [{"text": {"content": organisation}}]}
        if role:
            properties["Role"] = {"rich_text": [{"text": {"content": role}}]}
        if tags:
            properties["Tags"] = {"multi_select": [{"name": t} for t in tags]}
        if how_we_met:
            properties["How We Met"] = {"rich_text": [{"text": {"content": how_we_met}}]}
        if relationship_score:
            properties["Relationship"] = {"select": {"name": relationship_score}}
        if linkedin_url:
            properties["LinkedIn"] = {"url": linkedin_url}
        if notes:
            properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

        resp = self._client.request(
            path="pages",
            method="POST",
            body={"parent": {"database_id": db_id}, "properties": properties},
        )
        page_id = resp["id"]
        logger.info("Created Notion contact '%s' (page_id=%s)", name, page_id)
        return page_id

    def update_contact(self, page_id: str, **fields) -> None:
        """Update an existing Notion contact page by page_id."""
        properties = {}
        if "name" in fields:
            properties["Name"] = {"title": [{"text": {"content": fields["name"]}}]}
        if "email" in fields:
            properties["Email"] = {"email": fields["email"]}
        if "phone" in fields:
            properties["Phone"] = {"phone_number": fields["phone"]}
        if "organisation" in fields:
            properties["Organisation"] = {"rich_text": [{"text": {"content": fields["organisation"]}}]}
        if "role" in fields:
            properties["Role"] = {"rich_text": [{"text": {"content": fields["role"]}}]}
        if "tags" in fields:
            properties["Tags"] = {"multi_select": [{"name": t} for t in fields["tags"]]}
        if "how_we_met" in fields:
            properties["How We Met"] = {"rich_text": [{"text": {"content": fields["how_we_met"]}}]}
        if "relationship_score" in fields:
            properties["Relationship"] = {"select": {"name": fields["relationship_score"]}}
        if "linkedin_url" in fields:
            properties["LinkedIn"] = {"url": fields["linkedin_url"]}
        if "notes" in fields:
            properties["Notes"] = {"rich_text": [{"text": {"content": fields["notes"]}}]}

        self._client.request(
            path=f"pages/{page_id}",
            method="PATCH",
            body={"properties": properties},
        )
        logger.info("Updated Notion contact page %s", page_id)

    def create_task(
        self,
        title: str,
        status: str = "Not started",
        priority: str = "",
        due_date: str = "",
    ) -> str:
        """Create a new task in the Notion Tasks DB. Returns the new page ID."""
        db_id = self._db_ids.get("tasks", "")
        if not db_id:
            raise ValueError("Notion tasks database ID not configured in settings.yaml")

        properties = {
            "Task name": {"title": [{"text": {"content": title}}]},
        }
        if status:
            properties["Status"] = {"status": {"name": status}}
        if due_date:
            properties["Due date"] = {"date": {"start": due_date}}

        resp = self._client.request(
            path="pages",
            method="POST",
            body={"parent": {"database_id": db_id}, "properties": properties},
        )
        page_id = resp["id"]
        logger.info("Created Notion task '%s' (page_id=%s)", title, page_id)
        return page_id

    def create_goal(
        self,
        title: str,
        status: str = "active",
        deadline: str = "",
        description: str = "",
    ) -> str:
        """Create a new goal in the Notion Goals DB. Returns the new page ID."""
        db_id = self._db_ids.get("goals", "")
        if not db_id:
            raise ValueError("Notion goals database ID not configured in settings.yaml")

        properties = {
            "Goal": {"title": [{"text": {"content": title}}]},
        }
        if status:
            properties["Status"] = {"select": {"name": status.capitalize()}}
        if deadline:
            properties["Target Date"] = {"date": {"start": deadline}}

        resp = self._client.request(
            path="pages",
            method="POST",
            body={"parent": {"database_id": db_id}, "properties": properties},
        )
        page_id = resp["id"]
        logger.info("Created Notion goal '%s' (page_id=%s)", title, page_id)
        return page_id


# -- Discussion parsing helpers ------------------------------------------------

def _parse_discussion_title(title: str) -> tuple[str, str]:
    """
    Extract (date, medium) from titles like:
      "2026-03-15 -- Call"  /  "2026-03-15 meeting"  /  "2026-03-15"
    Returns ("", "") if no ISO date found at the start.
    """
    import re
    match = re.match(r"(\d{4}-\d{2}-\d{2})", title.strip())
    if not match:
        return "", ""
    date = match.group(1)
    rest = title[match.end():].lower()
    medium = "meeting"
    for keyword in ("call", "email", "message", "chat", "lunch", "coffee"):
        if keyword in rest:
            medium = keyword
            break
    return date, medium


def _extract_text_from_blocks(blocks: list) -> str:
    """Flatten a list of Notion block objects into a plain-text string."""
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        content = block.get(btype, {})
        rich = content.get("rich_text", [])
        text = "".join(r.get("plain_text", "") for r in rich)
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)
