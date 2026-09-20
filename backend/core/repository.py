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
from backend.config import SKILLS_DB_PATH, SIMILARITY_THRESHOLD, TAXONOMY_ALIASES
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

            # Action conflict guard: prevent false matching between conflicting transformations (e.g. lowercase vs camel vs uppercase)
            q_lower = task_description.lower()
            s_lower = (skill["task_description"] + " " + skill["name"] + " " + skill["subtask"]).lower()
            action_groups = [
                {"lowercase", "lower"},
                {"uppercase", "upper", "capital"},
                {"camel", "camelcase"},
                {"snake", "snake_case"},
                {"title", "titlecase"}
            ]
            has_conflict = False
            for grp in action_groups:
                q_in_grp = any(w in q_lower for w in grp)
                s_in_grp = any(w in s_lower for w in grp)
                if q_in_grp and not s_in_grp:
                    # Query explicitly wants this casing, but skill has a different casing action
                    if any(any(w in s_lower for w in other_grp) for other_grp in action_groups if other_grp != grp):
                        has_conflict = True
                        break
            if has_conflict:
                continue

            # Column/Entity target guard: prevent false matching across different columns (e.g. salary vs department vs city)
            stopwords = {
                "make", "the", "column", "columns", "to", "in", "dataframe", "df",
                "function", "task", "and", "a", "an", "as", "of", "all", "each", "every",
                "convert", "set", "change", "transform", "value", "values", "names", "name"
            }
            import re as _re
            q_tokens = set(_re.findall(r'[a-z0-9_]+', q_lower)) - stopwords
            s_tokens = set(_re.findall(r'[a-z0-9_]+', s_lower)) - stopwords
            action_words = {"lowercase", "lower", "uppercase", "upper", "camel", "camelcase", "snake", "snake_case", "clean", "impute", "drop", "bonus", "total"}
            q_targets = q_tokens - action_words
            s_targets = s_tokens - action_words

            # If query targets specific column(s) (e.g. 'salary') and skill targets different column(s) (e.g. 'department'):
            if q_targets and s_targets and not (q_targets & s_targets):
                continue

            # If query does not mention specific column but skill is bound to a specific column, don't false match
            if not q_targets and s_targets and any(w in q_lower for w in action_words):
                continue

            score = self.embedding_engine.semantic_similarity(
                task_description,
                skill["task_description"],
                target_vec
            )

            # Extra subtask and taxonomy alias match bonus
            subtask_query = task_description.lower()
            skill_sub = skill["subtask"].lower()
            skill_alias = TAXONOMY_ALIASES.get(skill_sub, skill_sub).lower()
            skill_name_lower = skill["name"].lower()

            if skill_sub in subtask_query or subtask_query in skill_sub or skill_alias in subtask_query:
                score = max(score, 0.95)
            elif skill_sub in subtask_query.replace("_", " ") or skill_alias in subtask_query.replace("_", " ") or skill_name_lower in subtask_query:
                score = max(score, 0.90)
            elif skill_sub in subtask_query or subtask_query in skill_sub:
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

    def seed_core_skills(self):
        """Seeds the foundational skills notebook for live evaluation and demo."""
        core_notebook_skills = [
            {
                "name": "remove_duplicates",
                "domain": "tabular_cleaning",
                "subtask": "remove_duplicates",
                "task_description": "remove_duplicates: remove duplicate records in dataframe",
                "code": '''def remove_duplicates(df):
    """
    Detects and eliminates duplicate rows in DataFrame, resetting row index.
    """
    import pandas as pd
    return df.drop_duplicates().reset_index(drop=True)
''',
                "entrypoint": "remove_duplicates",
                "validation_status": "validated",
                "validation_accuracy": 1.0,
                "visibility": "shared",
                "created_in_session": "system_seed"
            },
            {
                "name": "fill_missing_values",
                "domain": "tabular_cleaning",
                "subtask": "fill_missing_values",
                "task_description": "fill_missing_values: impute missing values in dataframe",
                "code": '''def fill_missing_values(df):
    """
    Imputes missing values: median for numeric columns, mode for categorical columns.
    """
    import pandas as pd
    import numpy as np
    cleaned_df = df.copy()
    for col in cleaned_df.columns:
        if cleaned_df[col].isnull().sum() > 0:
            if pd.api.types.is_numeric_dtype(cleaned_df[col]):
                med = cleaned_df[col].median()
                cleaned_df[col] = cleaned_df[col].fillna(med if not pd.isna(med) else 0)
            else:
                mode_series = cleaned_df[col].mode()
                mode_val = mode_series.iloc[0] if not mode_series.empty else "Unknown"
                cleaned_df[col] = cleaned_df[col].fillna(mode_val)
    return cleaned_df
''',
                "entrypoint": "fill_missing_values",
                "validation_status": "validated",
                "validation_accuracy": 1.0,
                "visibility": "shared",
                "created_in_session": "system_seed"
            },
            {
                "name": "detect_outliers",
                "domain": "tabular_cleaning",
                "subtask": "detect_outliers",
                "task_description": "detect_outliers: detect and handle outliers in numerical columns using IQR fences",
                "code": '''def detect_outliers(df):
    """
    Detects numerical outliers using IQR (1.5 * IQR) and caps them to lower and upper boundary fences.
    """
    import pandas as pd
    import numpy as np
    cleaned_df = df.copy()
    for col in cleaned_df.select_dtypes(include=[np.number]).columns:
        valid_series = cleaned_df[col].dropna()
        if len(valid_series) > 4:
            q1 = valid_series.quantile(0.25)
            q3 = valid_series.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                cleaned_df[col] = cleaned_df[col].clip(lower=q1 - 1.5 * iqr, upper=q3 + 1.5 * iqr)
    return cleaned_df
''',
                "entrypoint": "detect_outliers",
                "validation_status": "validated",
                "validation_accuracy": 1.0,
                "visibility": "shared",
                "created_in_session": "system_seed"
            },
            {
                "name": "normalize_columns",
                "domain": "tabular_cleaning",
                "subtask": "normalize_columns",
                "task_description": "normalize_columns: standardize and normalize column headers to clean snake_case",
                "code": '''def normalize_columns(df):
    """
    Converts DataFrame headers to clean snake_case: trimmed, lowercased, spaces/symbols to underscores.
    """
    import pandas as pd
    import re
    cleaned_df = df.copy()
    new_cols = []
    for c in cleaned_df.columns:
        name = str(c).strip().lower()
        name = re.sub(r'[\\s\\-\\.]+', '_', name)
        name = re.sub(r'[^a-z0-9_]', '', name)
        name = re.sub(r'_+', '_', name).strip('_')
        new_cols.append(name if name else 'col')
    cleaned_df.columns = new_cols
    return cleaned_df
''',
                "entrypoint": "normalize_columns",
                "validation_status": "validated",
                "validation_accuracy": 1.0,
                "visibility": "shared",
                "created_in_session": "system_seed"
            }
        ]
        for sk in core_notebook_skills:
            if not self.search_skills("tabular_cleaning", sk["task_description"], threshold=0.90):
                self.add_skill(sk)


_repo = None

def get_repository() -> SkillRepository:
    global _repo
    if _repo is None:
        _repo = SkillRepository()
    return _repo