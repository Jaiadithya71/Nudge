"""
config.py — Loads settings.yaml from the project root.
All connectors import from here instead of hardcoding paths and IDs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
_settings: dict = {}


def _load() -> dict:
    path = _ROOT / "settings.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get(key_path: str, default: Any = None) -> Any:
    """
    Dot-notation read from settings.yaml.
    e.g. get('integrations.notion.databases.tasks')
    """
    global _settings
    if not _settings:
        _settings = _load()
    parts = key_path.split(".")
    val = _settings
    for p in parts:
        if not isinstance(val, dict) or p not in val:
            return default
        val = val[p]
    return val


def project_root() -> Path:
    return _ROOT
