"""
tasks_connector.py - Fetches live tasks from the Notion Todo List database.
"""

import os
import logging
import requests
from datetime import date
from typing import List, Dict, Any
from dotenv import load_dotenv

from input.config import get

logger = logging.getLogger(__name__)


class TaskConnector:
    def __init__(self):
        load_dotenv()
        self.api_key     = os.environ.get("NOTION_API_KEY", "")
        self.database_id = get("integrations.notion.databases.tasks",
                               "30ecefe4ebef80509043f92275212665")
        self.base_url    = "https://api.notion.com/v1"
        self.headers     = {
            "Authorization":  f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type":   "application/json",
        }

    def fetch_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("NOTION_API_KEY not set — skipping tasks fetch.")
            return []

        logger.info("Fetching Notion tasks from database %s", self.database_id)
        try:
            response = requests.post(
                f"{self.base_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json={"page_size": 50},
                timeout=8,
            )
            response.raise_for_status()

            tasks = []
            for page in response.json().get("results", []):
                props = page.get("properties", {})

                title_parts = props.get("Task name", {}).get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts) or "Untitled Task"

                status_obj = props.get("Status", {}).get("status", {}) or {}
                status_raw = (status_obj.get("name") or "pending").lower()
                if "done" in status_raw or "complete" in status_raw:
                    internal_status = "completed"
                elif "overdue" in status_raw or "late" in status_raw:
                    internal_status = "overdue"
                else:
                    internal_status = "pending"

                date_obj = props.get("Due date", {}).get("date") or {}
                due_date = date_obj.get("start")

                # Auto-flag as overdue if due date has passed and task is still pending
                if internal_status == "pending" and due_date:
                    try:
                        due = date.fromisoformat(due_date[:10])
                        if due < date.today():
                            internal_status = "overdue"
                    except ValueError:
                        pass

                tasks.append({
                    "task_id": page.get("id"),
                    "title":   title,
                    "status":  internal_status,
                    "due_date": due_date,
                    "priority": "medium",
                })

            return tasks

        except Exception as exc:
            logger.error("Failed to fetch Notion tasks: %s", exc)
            return []
