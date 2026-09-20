"""
The 6-Stage Skill Lifecycle Engine.
Coordinates: Discover -> Synthesize -> Validate -> Execute -> Evaluate -> Promote/Reuse.
"""

import time
import uuid
import re
from typing import Dict, Any, List, Optional, Tuple
from backend.core.repository import get_repository
from backend.core.sandbox import get_sandbox
from backend.core.llm_synthesizer import get_synthesizer
from backend.core.metrics_store import get_metrics_store
from backend.datasets.tabular_benchmarks import get_held_out_tabular_test_cases
from backend.datasets.debugging_benchmarks import get_held_out_debugging_test_cases

class SkillLifecycleEngine:
    """Orchestrates autonomous skill learning, sandboxed validation, and reuse."""

    def __init__(self):
        self.repo = get_repository()
        self.sandbox = get_sandbox()
        self.synthesizer = get_synthesizer()
        self.metrics = get_metrics_store()

    def process_task(
        self,
        domain: str,
        subtask: str,
        task_name: str,
        task_description: str,
        execution_args: List[Any],
        execution_kwargs: Optional[Dict[str, Any]] = None,
        session_id: str = "default_session",
        held_out_test_cases: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executes the full 6-stage lifecycle for an incoming task.
        """
        start_time = time.perf_counter()
        execution_kwargs = execution_kwargs or {}

        # -------------------------------------------------------------
        # STAGE 1: DISCOVER
        # -------------------------------------------------------------
        existing_skill = self.repo.search_skills(
            domain=domain,
            task_description=f"{subtask}: {task_description}",
            session_id=session_id
        )

        lifecycle_status = "unknown"
        skill_id_used = None
        skill_name_used = None
        code_to_run = ""
        entrypoint_to_run = ""
        validation_report_dict = None
        prompt_tokens = 0
        completion_tokens = 0

        if existing_skill:
            # Reusing previously validated capability
            lifecycle_status = "reused"
            skill_id_used = existing_skill["skill_id"]
            skill_name_used = existing_skill["name"]
            code_to_run = existing_skill["code"]
            entrypoint_to_run = existing_skill["entrypoint"]
            badge = f"REUSED_SKILL (ID: {skill_id_used[:8]})"

        else:
            # ---------------------------------------------------------
            # STAGE 2: SYNTHESIZE
            # ---------------------------------------------------------
            synth_res = self.synthesizer.synthesize_skill(
                domain=domain,
                subtask=subtask,
                task_description=task_description
            )
            candidate_code = synth_res["code"]
            candidate_entry = synth_res["entrypoint"]
            prompt_tokens = synth_res.get("prompt_tokens", 400)
            completion_tokens = synth_res.get("completion_tokens", 200)

            # Retrieve held-out test suite for validation
            if held_out_test_cases is None:
                if domain == "tabular_cleaning":
                    held_out_test_cases = get_held_out_tabular_test_cases(subtask)
                else:
                    held_out_test_cases = get_held_out_debugging_test_cases(subtask)

            # ---------------------------------------------------------
            # STAGE 3: VALIDATE (SANDBOX GATE)
            # ---------------------------------------------------------
            val_report = self.sandbox.validate_skill(
                code_str=candidate_code,
                entrypoint=candidate_entry,
                held_out_test_cases=held_out_test_cases,
                pass_threshold=0.90
            )

            # Retry once with feedback if initial validation failed
            if val_report.status == "rejected" and val_report.is_safe:
                synth_retry = self.synthesizer.synthesize_skill(
                    domain=domain,
                    subtask=subtask,
                    task_description=task_description,
                    feedback_error=val_report.error_message
                )
                candidate_code = synth_retry["code"]
                candidate_entry = synth_retry["entrypoint"]
                prompt_tokens += synth_retry.get("prompt_tokens", 300)
                completion_tokens += synth_retry.get("completion_tokens", 150)

                val_report = self.sandbox.validate_skill(
                    code_str=candidate_code,
                    entrypoint=candidate_entry,
                    held_out_test_cases=held_out_test_cases,
                    pass_threshold=0.90
                )

            validation_report_dict = val_report.to_dict()

            if val_report.status == "validated":
                # -----------------------------------------------------
                # STAGE 6 (A): PROMOTE TO SHARED REPOSITORY
                # -----------------------------------------------------
                lifecycle_status = "synthesized_and_validated"
                skill_name_used = f"{subtask.replace('_', ' ').title()} Function"
                skill_id_used = self.repo.add_skill({
                    "name": skill_name_used,
                    "domain": domain,
                    "subtask": subtask,
                    "task_description": f"{subtask}: {task_description}",
                    "code": candidate_code,
                    "entrypoint": candidate_entry,
                    "validation_status": "validated",
                    "validation_accuracy": val_report.accuracy,
                    "created_in_session": session_id,
                    "visibility": "shared",
                    "usage_count": 0,
                    "success_count": 0,
                    "avg_execution_time_ms": val_report.execution_time_ms
                })
                code_to_run = candidate_code
                entrypoint_to_run = candidate_entry
                badge = f"NEWLY_LEARNED (Promoted ID: {skill_id_used[:8]})"

            else:
                # Skill was rejected — prevent unsafe/broken propagation
                lifecycle_status = "rejected_failed"
                self.repo.log_rejection({
                    "domain": domain,
                    "subtask": subtask,
                    "task_description": task_description,
                    "code": candidate_code,
                    "reason": val_report.error_message or "Validation threshold not met",
                    "failed_test_summary": val_report.test_results,
                    "created_in_session": session_id
                })
                total_latency = (time.perf_counter() - start_time) * 1000.0
                self.metrics.log_task(
                    session_id=session_id,
                    domain=domain,
                    subtask=subtask,
                    task_name=task_name,
                    lifecycle_status="rejected_failed",
                    skill_id_used=None,
                    skill_name_used=None,
                    success=False,
                    latency_ms=total_latency,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    details={"rejection_reason": val_report.error_message}
                )
                return {
                    "success": False,
                    "lifecycle_status": "rejected_failed",
                    "badge": "REJECTED_BY_SANDBOX",
                    "error": f"Skill failed sandbox validation: {val_report.error_message}",
                    "validation_report": validation_report_dict,
                    "latency_ms": round(total_latency, 2),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }

        # -------------------------------------------------------------
        # STAGE 4: EXECUTE
        # -------------------------------------------------------------
        exec_res = self.sandbox.execute_code(
            code_str=code_to_run,
            entrypoint=entrypoint_to_run,
            args=execution_args,
            kwargs=execution_kwargs
        )

        total_latency = (time.perf_counter() - start_time) * 1000.0

        # -------------------------------------------------------------
        # STAGE 5: EVALUATE & LOG TELEMETRY
        # -------------------------------------------------------------
        success = exec_res["success"]

        if lifecycle_status == "reused" and skill_id_used:
            self.repo.record_skill_usage(
                skill_id=skill_id_used,
                success=success,
                execution_time_ms=exec_res["execution_time_ms"],
                tokens_saved=1200
            )

        task_id = self.metrics.log_task(
            session_id=session_id,
            domain=domain,
            subtask=subtask,
            task_name=task_name,
            lifecycle_status=lifecycle_status,
            skill_id_used=skill_id_used,
            skill_name_used=skill_name_used,
            success=success,
            latency_ms=total_latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            details={
                "execution_time_ms": exec_res["execution_time_ms"],
                "error": exec_res.get("error"),
                "badge": badge
            }
        )

        return {
            "task_id": task_id,
            "success": success,
            "lifecycle_status": lifecycle_status,
            "badge": badge,
            "skill_id_used": skill_id_used,
            "skill_name_used": skill_name_used,
            "code_used": code_to_run,
            "entrypoint": entrypoint_to_run,
            "result": exec_res["result"],
            "error": exec_res.get("error"),
            "latency_ms": round(total_latency, 2),
            "execution_ms": round(exec_res["execution_time_ms"], 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "tokens_saved": 1200 if lifecycle_status == "reused" else 0,
            "validation_report": validation_report_dict
        }

    def process_dynamic_tabular_task(
        self,
        instruction: str,
        input_df: Any,
        session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """
        Executes the autonomous 6-stage lifecycle for ANY arbitrary natural language task
        on ANY arbitrary dataset:
        1. Discover: Checks the repository notebook to see if the skill is already memorized.
        2. Reuse: If found, executes immediately in the sandbox (0 LLM tokens, <15ms).
        3. Synthesize: If NOT found, uses LLM (Gemini or offline fallback) to generate code + test cases.
        4. Validate: Tests candidate code against held-out test cases in the secure sandbox.
        5. Memorize: If >= 90% accuracy, saves into the SQLite notebook (shared visibility).
        6. Execute: Runs the newly learned skill on the input DataFrame and logs metrics.
        """
        start_time = time.perf_counter()
        instr_clean = instruction.strip()
        instr_lower = instr_clean.lower()

        # Determine subtask identifier and human-friendly skill name
        if ("uppercase" in instr_lower and "city" in instr_lower) or "uppercase_city_names" in instr_lower:
            subtask = "uppercase_city_names"
            skill_name = "Uppercase City Names"
        elif "duplicate" in instr_lower and ("remove" in instr_lower or "drop" in instr_lower):
            subtask = "remove_duplicates"
            skill_name = "Remove Duplicates"
        elif "missing" in instr_lower or "impute" in instr_lower or "null" in instr_lower:
            subtask = "fill_missing_values"
            skill_name = "Fill Missing Values"
        elif "outlier" in instr_lower:
            subtask = "detect_outliers"
            skill_name = "Detect Outliers"
        elif "normalize" in instr_lower and "column" in instr_lower:
            subtask = "normalize_columns"
            skill_name = "Normalize Columns"
        else:
            slug = re.sub(r'[^a-zA-Z0-9_]+', '_', instr_lower)[:40].strip('_')
            subtask = slug if slug else "dynamic_transform"
            skill_name = instr_clean.replace("_", " ").title()
            if len(skill_name) > 45:
                skill_name = skill_name[:42] + "..."

        # -------------------------------------------------------------
        # STAGE 1: DISCOVER
        # -------------------------------------------------------------
        existing_skill = self.repo.search_skills(
            domain="tabular_cleaning",
            task_description=f"{subtask}: {instr_clean}",
            session_id=session_id
        )
        if not existing_skill:
            existing_skill = self.repo.search_skills(
                domain="tabular_cleaning",
                task_description=instr_clean,
                session_id=session_id
            )
        if not existing_skill and subtask:
            existing_skill = self.repo.search_skills(
                domain="tabular_cleaning",
                task_description=subtask,
                session_id=session_id
            )

        prompt_tokens = 0
        completion_tokens = 0
        tokens_saved = 0
        validation_report_dict = None

        if existing_skill:
            # Reusing previously validated capability from the notebook
            lifecycle_status = "reused"
            skill_id_used = existing_skill["skill_id"]
            skill_name_used = existing_skill["name"]
            code_to_run = existing_skill["code"]
            entrypoint_to_run = existing_skill["entrypoint"]
            badge = f"REUSED_SKILL (ID: {skill_id_used[:8]})"
            tokens_saved = 1200
        else:
            # ---------------------------------------------------------
            # STAGE 2: SYNTHESIZE
            # ---------------------------------------------------------
            if subtask == "uppercase_city_names":
                synth_res = self.synthesizer.synthesize_skill(
                    domain="tabular_cleaning",
                    subtask="uppercase_city_names",
                    task_description=instr_clean
                )
                candidate_code = synth_res["code"]
                candidate_entry = synth_res["entrypoint"]
                held_out_test_cases = get_held_out_tabular_test_cases("uppercase_city_names")
                prompt_tokens = synth_res.get("prompt_tokens", 450)
                completion_tokens = synth_res.get("completion_tokens", 250)
            else:
                synth_res = self.synthesizer.synthesize_arbitrary_tabular_skill(
                    df=input_df,
                    instruction=instr_clean
                )
                candidate_code = synth_res["code"]
                candidate_entry = synth_res["entrypoint"]
                held_out_test_cases = synth_res.get("test_cases", [])
                prompt_tokens = synth_res.get("prompt_tokens", 450)
                completion_tokens = synth_res.get("completion_tokens", 250)

            # ---------------------------------------------------------
            # STAGE 3: VALIDATE (SANDBOX GATE)
            # ---------------------------------------------------------
            val_report = self.sandbox.validate_skill(
                code_str=candidate_code,
                entrypoint=candidate_entry,
                held_out_test_cases=held_out_test_cases,
                pass_threshold=0.90
            )

            # Retry once with feedback if initial validation failed
            if val_report.status == "rejected" and val_report.is_safe:
                if subtask == "uppercase_city_names":
                    synth_retry = self.synthesizer.synthesize_skill(
                        domain="tabular_cleaning",
                        subtask="uppercase_city_names",
                        task_description=instr_clean,
                        feedback_error=val_report.error_message
                    )
                else:
                    synth_retry = self.synthesizer.synthesize_arbitrary_tabular_skill(
                        df=input_df,
                        instruction=instr_clean,
                        feedback_error=val_report.error_message
                    )
                candidate_code = synth_retry["code"]
                candidate_entry = synth_retry["entrypoint"]
                held_out_test_cases = synth_retry.get("test_cases", held_out_test_cases)
                prompt_tokens += synth_retry.get("prompt_tokens", 350)
                completion_tokens += synth_retry.get("completion_tokens", 150)

                val_report = self.sandbox.validate_skill(
                    code_str=candidate_code,
                    entrypoint=candidate_entry,
                    held_out_test_cases=held_out_test_cases,
                    pass_threshold=0.90
                )

            validation_report_dict = val_report.to_dict()

            if val_report.status == "validated":
                # -----------------------------------------------------
                # STAGE 6: PROMOTE TO SHARED NOTEBOOK (MEMORIZE)
                # -----------------------------------------------------
                lifecycle_status = "synthesized_and_validated"
                skill_id_used = self.repo.add_skill({
                    "name": skill_name,
                    "domain": "tabular_cleaning",
                    "subtask": subtask,
                    "task_description": f"{subtask}: {instr_clean}",
                    "code": candidate_code,
                    "entrypoint": candidate_entry,
                    "validation_status": "validated",
                    "validation_accuracy": val_report.accuracy,
                    "created_in_session": session_id,
                    "visibility": "shared",
                    "usage_count": 0,
                    "success_count": 0,
                    "avg_execution_time_ms": val_report.execution_time_ms
                })
                code_to_run = candidate_code
                entrypoint_to_run = candidate_entry
                skill_name_used = skill_name
                badge = f"NEWLY_LEARNED (Promoted ID: {skill_id_used[:8]})"
            else:
                lifecycle_status = "rejected_failed"
                self.repo.log_rejection({
                    "domain": "tabular_cleaning",
                    "subtask": subtask,
                    "task_description": instr_clean,
                    "code": candidate_code,
                    "reason": val_report.error_message or "Validation threshold not met",
                    "failed_test_summary": val_report.test_results,
                    "created_in_session": session_id
                })
                total_latency = (time.perf_counter() - start_time) * 1000.0
                self.metrics.log_task(
                    session_id=session_id,
                    domain="tabular_cleaning",
                    subtask=subtask,
                    task_name=f"Dynamic Tabular: {skill_name}",
                    lifecycle_status="rejected_failed",
                    skill_id_used=None,
                    skill_name_used=None,
                    success=False,
                    latency_ms=total_latency,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    details={"rejection_reason": val_report.error_message, "instruction": instr_clean}
                )
                return {
                    "success": False,
                    "lifecycle_status": "rejected_failed",
                    "badge": "REJECTED_BY_SANDBOX",
                    "subtask": subtask,
                    "skill_name_used": skill_name,
                    "error": f"Skill failed sandbox validation: {val_report.error_message}",
                    "validation_report": validation_report_dict,
                    "latency_ms": round(total_latency, 2),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }

        # -------------------------------------------------------------
        # STAGE 4: EXECUTE
        # -------------------------------------------------------------
        safe_df = input_df.copy(deep=True) if hasattr(input_df, "copy") else input_df
        exec_res = self.sandbox.execute_code(
            code_str=code_to_run,
            entrypoint=entrypoint_to_run,
            args=[safe_df],
            kwargs={}
        )

        total_latency = (time.perf_counter() - start_time) * 1000.0
        success = exec_res["success"]

        # -------------------------------------------------------------
        # STAGE 5: EVALUATE & LOG TELEMETRY
        # -------------------------------------------------------------
        if lifecycle_status == "reused" and skill_id_used:
            self.repo.record_skill_usage(
                skill_id=skill_id_used,
                success=success,
                execution_time_ms=exec_res["execution_time_ms"],
                tokens_saved=1200
            )

        task_id = self.metrics.log_task(
            session_id=session_id,
            domain="tabular_cleaning",
            subtask=subtask,
            task_name=f"Dynamic Tabular: {skill_name_used}",
            lifecycle_status=lifecycle_status,
            skill_id_used=skill_id_used,
            skill_name_used=skill_name_used,
            success=success,
            latency_ms=total_latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            details={
                "execution_time_ms": exec_res["execution_time_ms"],
                "error": exec_res.get("error"),
                "badge": badge,
                "instruction": instr_clean
            }
        )

        return {
            "task_id": task_id,
            "success": success,
            "lifecycle_status": lifecycle_status,
            "badge": badge,
            "subtask": subtask,
            "skill_id_used": skill_id_used,
            "skill_name_used": skill_name_used,
            "code_used": code_to_run,
            "entrypoint": entrypoint_to_run,
            "result": exec_res["result"],
            "error": exec_res.get("error"),
            "latency_ms": round(total_latency, 2),
            "execution_ms": round(exec_res["execution_time_ms"], 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "tokens_saved": tokens_saved,
            "validation_report": validation_report_dict
        }

_lifecycle = None

def get_lifecycle_engine() -> SkillLifecycleEngine:
    global _lifecycle
    if _lifecycle is None:
        _lifecycle = SkillLifecycleEngine()
    return _lifecycle