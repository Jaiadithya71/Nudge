
# MEMORY MODULE — DATABASE SCHEMA (schema.sql)

-- USERS (optional if needed for metadata)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- GOALS
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT CHECK(priority IN ('high','medium','low')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- TASKS
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT CHECK(status IN ('pending','completed','overdue')),
    due_date TIMESTAMP,
    goal_id TEXT,
    nudge_message TEXT,                        -- user-written nudge text for this task
    nudge_time TEXT,                           -- HH:MM — specific time to nudge (null = global schedule)
    nudge_enabled INTEGER DEFAULT 1,           -- 0 = nudging disabled for this task
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT DEFAULT 'notion',              -- 'notion' or 'local'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(goal_id) REFERENCES goals(id)
);

-- EVENTS
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CONTACTS
CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    last_interaction TIMESTAMP,
    importance_score REAL DEFAULT 0
);

-- USER ACTIONS (CRITICAL TABLE)
CREATE TABLE IF NOT EXISTS user_actions (
    id TEXT PRIMARY KEY,
    action_type TEXT,
    entity_type TEXT,
    entity_id TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BEHAVIOR PATTERNS
CREATE TABLE IF NOT EXISTS behavior_patterns (
    id TEXT PRIMARY KEY,
    pattern_type TEXT,
    description TEXT,
    confidence REAL,
    last_updated TIMESTAMP
);

-- GOAL ALIGNMENT
CREATE TABLE IF NOT EXISTS goal_alignment (
    id TEXT PRIMARY KEY,
    goal_id TEXT,
    entity_type TEXT,
    entity_id TEXT,
    alignment_score REAL,
    last_updated TIMESTAMP
);

-- NUDGE BANK (pre-generated nudge pool for the day — one LLM call per day)
CREATE TABLE IF NOT EXISTS nudge_bank (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    message TEXT,
    priority TEXT,
    for_date TEXT NOT NULL,   -- YYYY-MM-DD: regenerated each new day
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NUDGE LOG (persisted nudge history — survives server restarts)
CREATE TABLE IF NOT EXISTS nudge_log (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    message TEXT,
    priority TEXT,
    timing TEXT,
    job_type TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ORCHESTRATOR STATE (key-value store for scheduler metadata)
CREATE TABLE IF NOT EXISTS orchestrator_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- USER PREFERENCES (nudge schedule, limits, tone)
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    morning_time TEXT DEFAULT '07:00',   -- HH:MM
    midday_time  TEXT DEFAULT '12:00',
    evening_time TEXT DEFAULT '19:00',
    max_nudges_per_day INTEGER DEFAULT 5,
    min_gap_hours REAL DEFAULT 2.0,
    strictness REAL DEFAULT 0.7,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INDEXES (IMPORTANT FOR PERFORMANCE)
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_goal_id ON tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_actions_type ON user_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_time ON user_actions(created_at);
CREATE INDEX IF NOT EXISTS idx_patterns_type ON behavior_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_nudge_log_sent_at ON nudge_log(sent_at);
