# Phase 7: Extensibility and Data Ownership

> Prerequisite: Phases 1-5 (stable interfaces, proven architecture)
> Goal: Other developers can build modules. User data is portable.
> When complete: Nudge is a platform, not just an app.

---

## Why This Is Last

Extensibility requires stable interfaces. If the module API changes every phase (which it does), publishing a plugin interface is premature. Build it when the architecture is settled.

---

## Workstreams

### WS-EXT1: Plugin Architecture

**Module Interface:**
```python
class NudgePlugin:
    name: str                    # unique identifier
    version: str
    
    def register(self, memory, config) -> None:
        """Called on startup. Receive memory module handle and plugin config."""
    
    def ingest(self, user_id: str) -> None:
        """Called during sync. Fetch and store external data."""
    
    def get_context(self, user_id: str) -> dict:
        """Return context to be merged into UserContext for LLM."""
    
    def get_nudge_candidates(self, user_id: str, insight: dict) -> list[dict]:
        """Return nudge candidates based on plugin-specific logic."""
```

**Discovery:** Drop a Python file in `plugins/`. On startup, import all, call `register()`.

**Isolation:** Each plugin gets:
- Its own SQLite table prefix: `plugin_{name}_`
- Its own ChromaDB collection: `{user_id}_plugin_{name}`
- Its own config section in `settings.yaml`

**Example plugins:**
- `plugin_spotify.py` — track listening habits, nudge "time to focus" when playlist changes
- `plugin_github.py` — track PR reviews, nudge "you have pending reviews"
- `plugin_fitbit.py` — track activity, nudge "you've been sitting for 3 hours"

---

### WS-EXT2: Data Export

**Endpoint:** `GET /api/export`

Returns a ZIP containing:
```
export/
  mirror.db                 # complete SQLite database
  chroma/                   # ChromaDB directory (serialized)
  settings.yaml             # user's config
  preferences.json          # user's nudge preferences
  manifest.json             # export metadata: date, version, tables, row counts
```

**Format:** The SQLite file IS the data. No conversion needed. Any SQLite client can read it.

**Privacy:** The export includes everything. Add a `--redact` flag to strip:
- API keys from settings
- Push subscription endpoints
- Contact emails (replace with hashes)

---

### WS-EXT3: Data Import

**Endpoint:** `POST /api/import`

Accepts a ZIP from WS-EXT2 and hydrates a new user's database.

**Conflict resolution:** 
- New user: direct import
- Existing user: merge by ID, latest `last_modified` wins

---

## Phase 7 Success Criteria

1. A developer can write a plugin in a single Python file and drop it into `plugins/`
2. Plugin data is isolated from core data
3. Plugin nudges appear alongside core nudges (with attribution)
4. `GET /api/export` produces a complete, portable ZIP of all user data
5. `POST /api/import` restores a user from an export ZIP
6. SQLite database can be opened directly by any SQLite client for ad-hoc queries
