"""
Shared Skill Repository.
Stores validated skills, manages persistence with SQLite, executes
semantic discovery via embedding similarity, and isolates multi-session task state.
"""

import sqlite3
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from backend.config import SKILLS_DB_PATH, SIMILARITY_THRESHOLD
from backend.core.embedding_engine import get_embedding_engine

class SkillRepository:
    """Manages storage, semantic search, and metadata updates for learned skills."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or SKILLS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_engine = get_embedding_engine()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes database schema for skills and rejection logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                subtask TEXT NOT NULL,
                task_description TEXT NOT NULL,
                embedding TEXT NOT NULL,
                code TEXT NOT NULL,
                entrypoint TEXT NOT NULL,
                input_schema TEXT,
                output_schema TEXT,
                test_cases TEXT,
                validation_status TEXT NOT NULL,
                validation_accuracy REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                avg_execution_time_ms REAL DEFAULT 0.0,
                tokens_saved_estimate INTEGER DEFAULT 0,
                created_in_session TEXT NOT NULL,
                visibility TEXT DEFAULT 'shared',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejections (
                rejection_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                subtask TEXT NOT NULL,
                task_description TEXT NOT NULL,
                code TEXT,
                reason TEXT NOT NULL,
                failed_test_summary TEXT,
                created_in_session TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def add_skill(self, skill_data: Dict[str, Any]) -> str:
        """Stores a new validated skill into the repository."""
        skill_id = skill_data.get("skill_id") or str(uuid.uuid4())
        desc = skill_data.get("task_description", "")
        embedding = skill_data.get("embedding") or self.embedding_engine.compute_embedding(desc)
        now = datetime.datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO skills (
                skill_id, name, domain, subtask, task_description, embedding,
                code, entrypoint, input_schema, output_schema, test_cases,
                validation_status, validation_accuracy, usage_count, success_count,
                success_rate, avg_execution_time_ms, tokens_saved_estimate,
                created_in_session, visibility, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                skill_id,
                skill_data.get("name") or "Untitled Skill",
                skill_data.get("domain") or "general",
                skill_data.get("subtask") or "general",
                desc,
                json.dumps(embedding),
                skill_data.get("code") or "",
                skill_data.get("entrypoint") or "execute",
                json.dumps(skill_data.get("input_schema") or {}),
                json.dumps(skill_data.get("output_schema") or {}),
                json.dumps(skill_data.get("test_cases") or []),
                skill_data.get("validation_status") or "validated",
                float(skill_data.get("validation_accuracy") or 1.0),
                int(skill_data.get("usage_count") or 0),
                int(skill_data.get("success_count") or 0),
                float(skill_data.get("success_rate") or 1.0),
                float(skill_data.get("avg_execution_time_ms") or 0.0),
                int(skill_data.get("tokens_saved_estimate") or 0),
                skill_data.get("created_in_session") or "default",
                skill_data.get("visibility") or "shared",
                skill_data.get("created_at") or now,
                now
            ))
            conn.commit()
        return skill_id

    def log_rejection(self, rejection_data: Dict[str, Any]) -> str:
        """Logs an unreliable or unsafe skill that failed sandbox validation."""
        rejection_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO rejections (
                rejection_id, domain, subtask, task_description, code,
                reason, failed_test_summary, created_in_session, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rejection_id,
                rejection_data.get("domain", "general"),
                rejection_data.get("subtask", "general"),
                rejection_data.get("task_description", ""),
                rejection_data.get("code", ""),
                rejection_data.get("reason", "Failed validation"),
                json.dumps(rejection_data.get("failed_test_summary", {})),
                rejection_data.get("created_in_session", "default"),
                now
            ))
            conn.commit()
        return rejection_id

    def search_skills(
        self,
        domain: str,
        task_description: str,
        threshold: float = SIMILARITY_THRESHOLD,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Discovers a previously validated skill for the given task.
        Applies semantic similarity search and verifies visibility.
        """
        query_vec = self.embedding_engine.compute_embedding(task_description)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM skills
            WHERE domain = ? AND validation_status = 'validated'
            """, (domain,))
            rows = cursor.fetchall()

        best_skill = None
        best_score = -1.0

        for row in rows:
            skill = dict(row)
            # Visibility check: shared skills are visible to all sessions;
            # private skills are visible only to the owning session.
            if skill["visibility"] != "shared" and skill["created_in_session"] != session_id:
                continue

            try:
                target_vec = json.loads(skill["embedding"])
            except Exception:
                target_vec = None

            score = self.embedding_engine.semantic_similarity(
                task_description,
                skill["task_description"],
                target_vec
            )

            # Extra subtask exact match bonus
            subtask_query = task_description.lower()
            if skill["subtask"].lower() in subtask_query or subtask_query in skill["subtask"].lower():
                score = min(1.0, score + 0.15)

            if score > best_score:
                best_score = score
                best_skill = skill

        if best_skill and best_score >= threshold:
            best_skill["match_score"] = round(best_score, 4)
            best_skill["test_cases"] = json.loads(best_skill.get("test_cases") or "[]")
            best_skill["input_schema"] = json.loads(best_skill.get("input_schema") or "{}")
            best_skill["output_schema"] = json.loads(best_skill.get("output_schema") or "{}")
            return best_skill

        return None

    def record_skill_usage(
        self,
        skill_id: str,
        success: bool,
        execution_time_ms: float,
        tokens_saved: int = 1200
    ):
        """Updates metrics on reuse."""
        now = datetime.datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT usage_count, success_count, avg_execution_time_ms, tokens_saved_estimate FROM skills WHERE skill_id = ?", (skill_id,))
            row = cursor.fetchone()
            if not row:
                return

            usage_count = row["usage_count"] + 1
            success_count = row["success_count"] + (1 if success else 0)
            success_rate = round(success_count / usage_count, 4)
            # Running average of execution time
            prev_avg = row["avg_execution_time_ms"]
            new_avg = round(((prev_avg * (usage_count - 1)) + execution_time_ms) / usage_count, 2)
            tot_tokens = row["tokens_saved_estimate"] + tokens_saved

            cursor.execute("""
            UPDATE skills
            SET usage_count = ?, success_count = ?, success_rate = ?,
                avg_execution_time_ms = ?, tokens_saved_estimate = ?, updated_at = ?
            WHERE skill_id = ?
            """, (usage_count, success_count, success_rate, new_avg, tot_tokens, now, skill_id))
            conn.commit()

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills WHERE skill_id = ?", (skill_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["test_cases"] = json.loads(d.get("test_cases") or "[]")
                return d
        return None

    def list_skills(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if domain:
                cursor.execute("SELECT * FROM skills WHERE domain = ? ORDER BY created_at DESC", (domain,))
            else:
                cursor.execute("SELECT * FROM skills ORDER BY created_at DESC")
            rows = cursor.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["test_cases"] = json.loads(d.get("test_cases") or "[]")
                res.append(d)
            return res

    def list_rejections(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rejections ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def reset_repository(self):
        """Clears database for fresh evaluation runs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM skills")
            cursor.execute("DELETE FROM rejections")
            conn.commit()

_repo = None

def get_repository() -> SkillRepository:
    global _repo
    if _repo is None:
        _repo = SkillRepository()
    return _repo