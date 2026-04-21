"""
tests/test_memory.py — Unit tests for the Memory module.

Covers all scenarios from TEST_PLAN.md:
  - User isolation (no data leakage between users)
  - Idempotent ingestion (no duplicate rows)
  - Action logging
  - UserContext structure
  - Edge cases: empty user, large volume
  - Performance: build_user_context < 200ms
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest

# Make sure the parent directory is on the path so imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))

import memory
import db as db_module
import vector_db as vdb_module


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def fresh_user() -> str:
    """Each test gets its own isolated user."""
    return f"test_{uuid.uuid4().hex}"


def cleanup_user(user_id: str) -> None:
    """Release Chroma file handles, then remove the user's data directory."""
    import shutil
    # Release ChromaDB client first so Windows can delete the files
    try:
        vdb_module.reset_client(user_id)
    except Exception:
        pass
    import time
    time.sleep(0.1)  # brief pause for background threads to settle
    data_dir = Path(__file__).parent.parent / "data" / user_id
    if data_dir.exists():
        shutil.rmtree(data_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────
# User Isolation
# ─────────────────────────────────────────────────────────────────

class TestUserIsolation:
    def test_goals_do_not_leak_between_users(self):
        u1, u2 = fresh_user(), fresh_user()
        try:
            memory.ingest("goals", {"title": "User1 Goal", "priority": "high"}, u1)

            ctx_u2 = memory.build_user_context(u2)
            assert len(ctx_u2.goals) == 0, "u2 must not see u1's goals"
        finally:
            cleanup_user(u1)
            cleanup_user(u2)

    def test_tasks_do_not_leak_between_users(self):
        u1, u2 = fresh_user(), fresh_user()
        try:
            memory.ingest("tasks", {"title": "u1 task", "status": "pending"}, u1)

            ctx_u2 = memory.build_user_context(u2)
            assert len(ctx_u2.tasks) == 0
        finally:
            cleanup_user(u1)
            cleanup_user(u2)

    def test_actions_do_not_leak_between_users(self):
        u1, u2 = fresh_user(), fresh_user()
        try:
            memory.log_action(u1, {"action_type": "test_action"})

            ctx_u2 = memory.build_user_context(u2)
            assert len(ctx_u2.recent_actions) == 0
        finally:
            cleanup_user(u1)
            cleanup_user(u2)

    def test_semantic_search_does_not_leak_between_users(self):
        u1, u2 = fresh_user(), fresh_user()
        try:
            memory.ingest("goals", {"title": "Secret plan for u1"}, u1)
            results = memory.semantic_search(u2, "Secret plan")
            assert results == [], "u2's semantic search must not return u1's data"
        finally:
            cleanup_user(u1)
            cleanup_user(u2)


# ─────────────────────────────────────────────────────────────────
# Idempotent Ingestion
# ─────────────────────────────────────────────────────────────────

class TestIdempotentIngestion:
    def test_duplicate_goal_insert_does_not_duplicate(self):
        user = fresh_user()
        try:
            goal_id = str(uuid.uuid4())
            payload = {"id": goal_id, "title": "Idempotent Goal", "priority": "low"}
            memory.ingest("goals", payload, user)
            memory.ingest("goals", payload, user)  # same record again

            ctx = memory.build_user_context(user)
            matching = [g for g in ctx.goals if g.id == goal_id]
            assert len(matching) == 1, "duplicate insert must not create two rows"
        finally:
            cleanup_user(user)

    def test_duplicate_task_insert_does_not_duplicate(self):
        user = fresh_user()
        try:
            task_id = str(uuid.uuid4())
            payload = {"id": task_id, "title": "Task A", "status": "pending"}
            memory.ingest("tasks", payload, user)
            memory.ingest("tasks", payload, user)

            ctx = memory.build_user_context(user)
            matching = [t for t in ctx.tasks if t.id == task_id]
            assert len(matching) == 1
        finally:
            cleanup_user(user)

    def test_duplicate_action_insert_does_not_duplicate(self):
        user = fresh_user()
        try:
            action_id = str(uuid.uuid4())
            action = {"id": action_id, "action_type": "test"}
            memory.log_action(user, action)
            memory.log_action(user, action)

            ctx = memory.build_user_context(user)
            matching = [a for a in ctx.recent_actions if a.id == action_id]
            assert len(matching) == 1
        finally:
            cleanup_user(user)


# ─────────────────────────────────────────────────────────────────
# Action Logging
# ─────────────────────────────────────────────────────────────────

class TestActionLogging:
    def test_action_is_stored_correctly(self):
        user = fresh_user()
        try:
            action_id = str(uuid.uuid4())
            memory.log_action(user, {
                "id": action_id,
                "action_type": "click",
                "entity_type": "tasks",
                "entity_id": "task-123",
                "metadata": {"source": "ui"},
            })
            ctx = memory.build_user_context(user)
            action = next((a for a in ctx.recent_actions if a.id == action_id), None)
            assert action is not None
            assert action.action_type == "click"
            assert action.entity_type == "tasks"
        finally:
            cleanup_user(user)

    def test_action_without_explicit_id_gets_uuid(self):
        user = fresh_user()
        try:
            memory.log_action(user, {"action_type": "auto_id_test"})
            ctx = memory.build_user_context(user)
            assert any(a.action_type == "auto_id_test" for a in ctx.recent_actions)
        finally:
            cleanup_user(user)


# ─────────────────────────────────────────────────────────────────
# UserContext Structure
# ─────────────────────────────────────────────────────────────────

class TestContextBuild:
    def test_user_context_has_correct_user_id(self):
        user = fresh_user()
        try:
            ctx = memory.build_user_context(user)
            assert ctx.user_id == user
        finally:
            cleanup_user(user)

    def test_user_context_has_all_required_fields(self):
        from models import UserContext
        user = fresh_user()
        try:
            ctx = memory.build_user_context(user)
            assert isinstance(ctx, UserContext)
            assert hasattr(ctx, "goals")
            assert hasattr(ctx, "tasks")
            assert hasattr(ctx, "events")
            assert hasattr(ctx, "contacts")
            assert hasattr(ctx, "behavior_patterns")
            assert hasattr(ctx, "recent_actions")
            assert hasattr(ctx, "built_at")
        finally:
            cleanup_user(user)

    def test_ingested_data_appears_in_context(self):
        user = fresh_user()
        try:
            goal_id = str(uuid.uuid4())
            memory.ingest("goals", {"id": goal_id, "title": "My Goal", "priority": "high"}, user)
            ctx = memory.build_user_context(user)
            assert any(g.id == goal_id for g in ctx.goals)
        finally:
            cleanup_user(user)


# ─────────────────────────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_user_returns_empty_context(self):
        user = fresh_user()
        try:
            ctx = memory.build_user_context(user)
            assert ctx.goals == []
            assert ctx.tasks == []
            assert ctx.events == []
            assert ctx.contacts == []
            assert ctx.recent_actions == []
        finally:
            cleanup_user(user)

    def test_large_volume_ingestion(self):
        """Ingest 500 tasks and verify all are stored without data loss."""
        user = fresh_user()
        try:
            ids = [str(uuid.uuid4()) for _ in range(500)]
            for i, tid in enumerate(ids):
                memory.ingest("tasks", {"id": tid, "title": f"Task {i}", "status": "pending"}, user)
            ctx = memory.build_user_context(user)
            stored_ids = {t.id for t in ctx.tasks}
            assert stored_ids == set(ids), "All 500 tasks must be retrievable"
        finally:
            cleanup_user(user)

    def test_missing_user_id_raises(self):
        with pytest.raises((ValueError, Exception)):
            memory.build_user_context("")

    def test_unsupported_entity_type_raises(self):
        user = fresh_user()
        try:
            with pytest.raises(ValueError, match="Unsupported entity_type"):
                memory.ingest("unknown_entity", {"id": "x"}, user)
        finally:
            cleanup_user(user)


# ─────────────────────────────────────────────────────────────────
# Performance
# ─────────────────────────────────────────────────────────────────

class TestPerformance:
    def test_build_user_context_under_200ms(self):
        """build_user_context must complete in < 200ms (TEST_PLAN.md requirement)."""
        user = fresh_user()
        try:
            # Seed with some data to make the test realistic
            for _ in range(20):
                memory.ingest("goals", {"title": "perf goal", "priority": "medium"}, user)
                memory.ingest("tasks", {"title": "perf task", "status": "pending"}, user)

            start = time.perf_counter()
            memory.build_user_context(user)
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert elapsed_ms < 200, (
                f"build_user_context took {elapsed_ms:.1f}ms — must be < 200ms"
            )
        finally:
            cleanup_user(user)
