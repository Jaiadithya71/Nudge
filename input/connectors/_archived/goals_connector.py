"""
goals_connector.py - Fetches goals from the Notion Goals Hub database.

Property mapping (from live schema):
    Goal        → title  (title)
    Status      → status (select)
    Target Date → due date (date)
    Timeline    → timeline bucket (select: weekly/monthly/quarterly/yearly)
"""

import os
import logging
import requests
from typing import List, Dict, Any
from dotenv import load_dotenv

from input.config import get

logger = logging.getLogger(__name__)

# Map Notion Status select values → internal priority
_STATUS_PRIORITY: dict[str, str] = {
    "in progress": "high",
    "active":      "high",
    "not started": "medium",
    "on hold":     "low",
    "done":        "low",
    "complete":    "low",
}


class GoalsConnector:
    def __init__(self):
        load_dotenv()
        self.api_key     = os.environ.get("NOTION_API_KEY", "")
        self.database_id = get("integrations.notion.databases.goals",
                               "312cefe4ebef8161be87c0ac33df6d67")
        self.base_url    = "https://api.notion.com/v1"
        self.headers     = {
            "Authorization":  f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type":   "application/json",
        }

    def fetch_goals(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("NOTION_API_KEY not set — skipping goals fetch.")
            return []

        logger.info("Fetching Notion goals from database %s", self.database_id)
        try:
            response = requests.post(
                f"{self.base_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json={"page_size": 50},
                timeout=8,
            )
            response.raise_for_status()

            goals = []
            for page in response.json().get("results", []):
                props = page.get("properties", {})

                title_parts = props.get("Goal", {}).get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts) or "Untitled Goal"

                status_obj = props.get("Status", {}).get("select") or {}
                status_raw = (status_obj.get("name") or "").lower()

                priority = "medium"
                for key, val in _STATUS_PRIORITY.items():
                    if key in status_raw:
                        priority = val
                        break

                date_obj = props.get("Target Date", {}).get("date") or {}
                target_date = date_obj.get("start")

                timeline_obj = props.get("Timeline", {}).get("select") or {}
                timeline = (timeline_obj.get("name") or "").lower()

                # Build a description from the available fields
                description_parts = []
                if status_raw:
                    description_parts.append(f"Status: {status_raw}")
                if timeline:
                    description_parts.append(f"Timeline: {timeline}")
                if target_date:
                    description_parts.append(f"Target: {target_date}")

                goals.append({
                    "goal_id":    page.get("id"),
                    "title":      title,
                    "description": " | ".join(description_parts) or None,
                    "priority":   priority,
                    "status":     status_raw or "active",
                    "target_date": target_date,
                })

            return goals

        except Exception as exc:
            logger.error("Failed to fetch Notion goals: %s", exc)
            return []
