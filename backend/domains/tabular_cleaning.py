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
        session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """
        Plans and runs the multi-stage cleaning pipeline through the Skill Lifecycle Engine.
        """
        start_time = time.perf_counter()
        initial_profile = self.profile_dataframe(df)
        working_df = df.copy(deep=True)
        pipeline_trace = []
        total_tokens_saved = 0

        # Plan subtasks needed
        planned_subtasks = []

        # 1. Header standardization
        if initial_profile["dirty_column_names"]:
            planned_subtasks.append(("column_name_standardization", "standardize column headers to snake_case"))

        # 2. Duplicate removal
        if initial_profile["duplicate_rows"] > 0:
            planned_subtasks.append(("duplicate_removal", "remove duplicate rows in dataframe"))

        # 3. Type coercion
        if initial_profile["coercion_candidates"]:
            planned_subtasks.append(("type_coercion", "coerce dirty numeric and currency strings to float"))

        # 4. Missing value imputation
        if initial_profile["total_nulls"] > 0:
            planned_subtasks.append(("missing_value_imputation", "impute missing values with median or mode"))

        # 5. Outlier handling
        if initial_profile["outlier_candidates"]:
            planned_subtasks.append(("outlier_handling", "cap extreme numerical outliers using IQR fences"))

        # 6. Date normalization
        if initial_profile["date_candidates"]:
            planned_subtasks.append(("date_parsing_normalization", "normalize date strings to ISO-8601"))

        # Always run basic pipeline if no specific anomaly detected
        if not planned_subtasks:
            planned_subtasks = [
                ("column_name_standardization", "standardize column headers to snake_case"),
                ("missing_value_imputation", "impute missing values with median or mode")
            ]

        # Execute planned subtasks through the 6-stage lifecycle
        for subtask, desc in planned_subtasks:
            step_res = self.lifecycle.process_task(
                domain="tabular_cleaning",
                subtask=subtask,
                task_name=f"Tabular Pipeline: {subtask}",
                task_description=desc,
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
                "tokens_saved": step_res.get("tokens_saved", 0)
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

        return {
            "success": True,
            "cleaned_dataframe": working_df,
            "cleaned_records": working_df.to_dict(orient="records"),
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