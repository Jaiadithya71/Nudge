# llm_module

Converts a `UserContext` dict into a structured `Insight` dict using **Gemini 2.5 Pro**.
Supports a `mock` mode for deterministic, offline testing.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

Copy `.env.example` to `.env` and paste your Gemini API key:

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=<your key>
# Get a key at: https://aistudio.google.com/app/apikey
```

### 3. Use the module

```python
from llm_module import generate_insight

context = {
    "goals": ["Ship feature X by Q2"],
    "tasks": [
        {"id": 1, "name": "Write unit tests", "status": "in_progress"},
    ],
    "recent_actions": ["Committed code", "Attended standup"],
    "behavior_patterns": ["Morning focus block"],
    "daily_summary": "Productive morning. Afternoon scattered.",
}

# Real mode — calls Gemini 2.5 Pro
insight = generate_insight(context, mode="real")

# Mock mode — deterministic, no network call
insight = generate_insight(context, mode="mock")

print(insight["summary"])
print(insight["key_observations"])
```

---

## API

### `generate_insight(context, mode="real") -> dict`

| Param | Type | Description |
|-------|------|-------------|
| `context` | `dict` | Must match `UserContext` schema (see below) |
| `mode` | `str` | `"real"` or `"mock"` |

**Returns:** A dict matching the `Insight` schema.

**Raises:**
- `ValueError` — invalid mode or missing context fields
- `ValidationError` — LLM returned invalid output after 3 retries
- `EnvironmentError` — `GEMINI_API_KEY` not set (real mode only)

---

## Schemas

### UserContext (input)

| Field | Type | Description |
|-------|------|-------------|
| `goals` | `List[str]` | User's stated goals |
| `tasks` | `List[dict]` | Active/recent tasks |
| `recent_actions` | `List[str]` | Recent user actions |
| `behavior_patterns` | `List[str]` | Observed patterns |
| `daily_summary` | `str` | Free-text daily summary |

### Insight (output)

| Field | Type | Description |
|-------|------|-------------|
| `insight_id` | `str` | UUID for this insight |
| `summary` | `str` | 2–3 sentence assessment |
| `key_observations` | `List[str]` | Specific observations |
| `goal_alignment` | `str` | Alignment evaluation |
| `behavior_flags` | `List[str]` | Red-flag behaviours |
| `opportunity_areas` | `List[str]` | Improvement opportunities |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes (real mode) | — | Your Google AI API key |
| `GEMINI_MODEL` | No | `gemini-2.5-pro-preview-03-25` | Model to use |

---

## Running Tests

```bash
pytest tests/ -v
```

All tests use `mock` mode or patch the LLM client — no API key required to run the test suite.

---

## Project Structure

```
llm_module/
├── llm_module/
│   ├── __init__.py      ← generate_insight() public API
│   ├── schemas.py       ← UserContext + Insight TypedDicts
│   ├── prompt.py        ← prompt builder
│   ├── llm_client.py    ← Gemini 2.5 client
│   ├── mock_client.py   ← deterministic mock
│   └── validator.py     ← JSON parse + schema validation
├── tests/
│   ├── conftest.py
│   ├── test_valid_output.py
│   ├── test_invalid_json.py
│   ├── test_missing_fields.py
│   ├── test_mock_mode.py
│   └── test_edge_cases.py
├── .env                 ← your keys (gitignored)
├── .env.example         ← template
├── requirements.txt
└── README.md
```
