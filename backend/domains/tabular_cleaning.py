"""
Domain Agent 1: Tabular Data Cleaning.
Profiles messy CSV datasets, formulates cleaning plans across 6 taxonomy subtasks,
executes each stage through the Skill Lifecycle Engine, and produces comprehensive diff reports.
"""

import time
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from backend.core.skill_lifecycle import get_lifecycle_engine

class TabularCleaningAgent:
    """Autonomous agent for dirty tabular data profiling, planning, and cleaning."""

    def __init__(self):
        self.lifecycle = get_lifecycle_engine()

    def profile_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyzes anomalies, dirty types, missing values, duplicates, and outliers."""
        profile = {
            "row_count": len(df),
            "col_count": len(df.columns),
            "columns": list(df.columns),
            "total_nulls": int(df.isnull().sum().sum()),
            "nulls_per_col": {col: int(df[col].isnull().sum()) for col in df.columns if df[col].isnull().sum() > 0},
            "duplicate_rows": int(df.duplicated().sum()),
            "dirty_column_names": [c for c in df.columns if c != c.strip().lower().replace(" ", "_").replace("-", "_")],
            "coercion_candidates": [],
            "outlier_candidates": [],
            "date_candidates": []
        }

        # Check for dirty object types that could be numeric
        for col in df.columns:
            if df[col].dtype == "object":
                sample = df[col].dropna().astype(str)
                if not sample.empty:
                    if sample.str.contains(r"[\$,€,£,%]", regex=True).any():
                        profile["coercion_candidates"].append(col)
                    elif sample.str.contains(r"[-/.]", regex=True).mean() > 0.6:
                        # Check if matches date-like structure
                        profile["date_candidates"].append(col)

        # Check for outliers in numeric columns
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) > 4:
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outliers = int(((series < (q1 - 1.5 * iqr)) | (series > (q3 + 1.5 * iqr))).sum())
                    if outliers > 0:
                        profile["outlier_candidates"].append({"column": col, "outliers_count": outliers})

        return profile

    def clean_dataset(
        self,
        df: pd.DataFrame,
        session_id: str = "default_session",
        instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Plans and runs the multi-stage cleaning pipeline through the Skill Lifecycle Engine.
        Supports natural language instruction or automated profile-driven cleaning.
        """
        start_time = time.perf_counter()
        initial_profile = self.profile_dataframe(df)
        working_df = df.copy(deep=True)
        pipeline_trace = []
        total_tokens_saved = 0

        # Parse user instruction
        instr_clean = (instruction or "").strip()
        instr_lower = instr_clean.lower()
        has_uppercase_city = ("uppercase" in instr_lower and "city" in instr_lower) or "uppercase_city_names" in instr_lower
        is_clean_cmd = ("clean" in instr_lower) or (not instr_clean) or ("dataset" in instr_lower)

        # Plan subtasks needed
        planned_subtasks = []

        if has_uppercase_city and not is_clean_cmd:
            # User specifically requested the new skill: uppercase_city_names
            planned_subtasks.append(("uppercase_city_names", "convert every city name into uppercase"))

        elif has_uppercase_city and is_clean_cmd:
            # User requested cleaning + new skill
            if initial_profile["duplicate_rows"] > 0 or "duplicate" in instr_lower:
                planned_subtasks.append(("remove_duplicates", "remove duplicate records in dataframe"))
            if initial_profile["total_nulls"] > 0 or "missing" in instr_lower:
                planned_subtasks.append(("fill_missing_values", "impute missing values in dataframe"))
            planned_subtasks.append(("uppercase_city_names", "convert every city name into uppercase"))

        else:
            # Profile-driven cleaning pipeline
            # 1. Header standardization
            if initial_profile["dirty_column_names"]:
                planned_subtasks.append(("normalize_columns", "standardize and normalize column headers to clean snake_case"))

            # 2. Duplicate removal
            if initial_profile["duplicate_rows"] > 0 or "duplicate" in instr_lower:
                planned_subtasks.append(("remove_duplicates", "remove duplicate records in dataframe"))

            # 3. Type coercion
            if initial_profile["coercion_candidates"]:
                planned_subtasks.append(("type_coercion", "coerce dirty numeric and currency strings to float"))

            # 4. Missing value imputation
            if initial_profile["total_nulls"] > 0 or "missing" in instr_lower or "null" in instr_lower:
                planned_subtasks.append(("fill_missing_values", "impute missing values in dataframe"))

            # 5. Outlier handling
            if initial_profile["outlier_candidates"] or "outlier" in instr_lower:
                planned_subtasks.append(("detect_outliers", "detect and handle outliers in numerical columns using IQR fences"))

            # 6. Date normalization
            if initial_profile["date_candidates"] or "date" in instr_lower:
                planned_subtasks.append(("date_parsing_normalization", "normalize date strings to ISO-8601"))

            # Fallback if no specific anomalies flagged
            if not planned_subtasks:
                planned_subtasks = [
                    ("remove_duplicates", "remove duplicate records in dataframe"),
                    ("fill_missing_values", "impute missing values in dataframe")
                ]

        # Execute planned subtasks through the 6-stage lifecycle
        for subtask, desc in planned_subtasks:
            step_res = self.lifecycle.process_task(
                domain="tabular_cleaning",
                subtask=subtask,
                task_name=f"Tabular Pipeline: {subtask}",
                task_description=f"{subtask}: {desc}",
                execution_args=[working_df],
                session_id=session_id
            )

            if step_res["success"] and isinstance(step_res["result"], pd.DataFrame):
                working_df = step_res["result"]

            total_tokens_saved += step_res.get("tokens_saved", 0)

            pipeline_trace.append({
                "subtask": subtask,
                "description": desc,
                "lifecycle_status": step_res["lifecycle_status"],
                "badge": step_res["badge"],
                "skill_id": step_res.get("skill_id_used"),
                "skill_name": step_res.get("skill_name_used"),
                "success": step_res["success"],
                "latency_ms": step_res["latency_ms"],
                "tokens_saved": step_res.get("tokens_saved", 0),
                "validation_report": step_res.get("validation_report")
            })

        final_profile = self.profile_dataframe(working_df)
        total_pipeline_time_ms = (time.perf_counter() - start_time) * 1000.0

        # Build statistical diff report
        diff_report = {
            "initial_rows": initial_profile["row_count"],
            "final_rows": final_profile["row_count"],
            "rows_removed": initial_profile["row_count"] - final_profile["row_count"],
            "initial_nulls": initial_profile["total_nulls"],
            "final_nulls": final_profile["total_nulls"],
            "nulls_resolved": initial_profile["total_nulls"] - final_profile["total_nulls"],
            "initial_duplicates": initial_profile["duplicate_rows"],
            "final_duplicates": final_profile["duplicate_rows"],
            "duplicates_removed": initial_profile["duplicate_rows"] - final_profile["duplicate_rows"],
            "columns_renamed": len(initial_profile["dirty_column_names"]),
            "pipeline_time_ms": round(total_pipeline_time_ms, 2),
            "total_tokens_saved": total_tokens_saved,
            "steps_executed": len(pipeline_trace),
            "reused_steps": sum(1 for s in pipeline_trace if s["lifecycle_status"] == "reused"),
            "newly_learned_steps": sum(1 for s in pipeline_trace if s["lifecycle_status"] == "synthesized_and_validated")
        }

        # Ensure NaN values are converted to None for strict JSON serialization
        import json as _json
        json_safe_records = _json.loads(working_df.to_json(orient="records"))

        return {
            "success": True,
            "cleaned_dataframe": working_df,
            "cleaned_records": json_safe_records,
            "cleaned_columns": list(working_df.columns),
            "diff_report": diff_report,
            "pipeline_trace": pipeline_trace,
            "initial_profile": initial_profile,
            "final_profile": final_profile
        }

_agent = None

def get_tabular_agent() -> TabularCleaningAgent:
    global _agent
    if _agent is None:
        _agent = TabularCleaningAgent()
    return _agent