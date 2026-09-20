"""
Comprehensive End-to-End Test Suite for Self-Evolving Agentic AI Workbench.
Covers: AST Sandbox Isolation, Repository Vector Matching, Lifecycle Promotion & Reuse,
Tabular Profiling & Cleaning, Code Defect Repair, and Multi-Session Data Isolation.
"""

import pytest
import pandas as pd
import numpy as np
from backend.core.sandbox import get_sandbox
from backend.core.repository import get_repository
from backend.core.embedding_engine import get_embedding_engine
from backend.core.skill_lifecycle import get_lifecycle_engine
from backend.core.metrics_store import get_metrics_store
from backend.domains.tabular_cleaning import get_tabular_agent
from backend.domains.code_debugging import get_debugging_agent
from backend.datasets.tabular_benchmarks import generate_sample_dirty_dataset, get_held_out_tabular_test_cases
from backend.datasets.debugging_benchmarks import DEBUGGING_BENCHMARKS, get_held_out_debugging_test_cases

def test_ast_sandbox_security():
    """Verify that dangerous operations and imports are blocked at AST inspection time."""
    sb = get_sandbox()

    malicious_snippets = [
        "import os\nos.system('dir')",
        "import subprocess\nsubprocess.run(['ls'])",
        "import socket\nsocket.socket()",
        "import shutil\nshutil.rmtree('.')",
        "x = eval('2 + 2')",
        "x = exec('print(1)')",
        "class A: pass\nA.__subclasses__()"
    ]

    for snippet in malicious_snippets:
        is_safe, violations = sb.check_safety(snippet)
        assert not is_safe, f"Failed to block unsafe snippet: {snippet}"
        assert len(violations) > 0

    # Safe snippet must pass
    safe_snippet = "def calculate(a, b):\n    return a * b + 10"
    is_safe, violations = sb.check_safety(safe_snippet)
    assert is_safe
    assert len(violations) == 0


def test_sandbox_execution_and_timeout():
    """Verify sandbox runs valid code and catches infinite loops with timeout."""
    sb = get_sandbox()
    # 1. Valid execution
    res = sb.execute_code("def add(x, y):\n    return x + y", "add", [15, 27])
    assert res["success"] is True
    assert res["result"] == 42
    assert res["execution_time_ms"] > 0

    # 2. Timeout protection
    long_code = "def slow_fn():\n    import time\n    time.sleep(3)\n    return 'done'"
    prev_timeout = sb.timeout_seconds
    sb.timeout_seconds = 0.5
    try:
        res_timeout = sb.execute_code(long_code, "slow_fn", [])
        assert res_timeout["success"] is False
        assert "Timed Out" in res_timeout["error"]
    finally:
        sb.timeout_seconds = prev_timeout


def test_semantic_embedding_engine():
    """Verify semantic vectorizer assigns significantly higher similarity to related subtasks."""
    engine = get_embedding_engine()
    q = "missing_value_imputation: impute missing values with median in dataframe"
    target_same = "missing_value_imputation: clean missing numeric values using median"
    target_diff = "off_by_one_fix: fix off by one loop boundary error"

    score_same = engine.semantic_similarity(q, target_same)
    score_diff = engine.semantic_similarity(q, target_diff)

    assert score_same > 0.35
    assert score_diff < 0.20
    assert score_same > score_diff * 2


def test_skill_repository_lifecycle():
    """Verify repository storage, retrieval, and rejection logging."""
    repo = get_repository()
    repo.reset_repository()

    skill_id = repo.add_skill({
        "name": "Median Imputer",
        "domain": "tabular_cleaning",
        "subtask": "missing_value_imputation",
        "task_description": "missing_value_imputation: impute numeric missing values with median",
        "code": "def impute(df): return df.fillna(df.median())",
        "entrypoint": "impute",
        "validation_status": "validated",
        "validation_accuracy": 1.0,
        "created_in_session": "session_alpha",
        "visibility": "shared"
    })
    assert skill_id is not None

    # Discover skill
    found = repo.search_skills("tabular_cleaning", "missing_value_imputation: impute numeric missing values with median")
    assert found is not None
    assert found["skill_id"] == skill_id

    # Record usage
    repo.record_skill_usage(skill_id, success=True, execution_time_ms=12.5)
    updated = repo.get_skill(skill_id)
    assert updated["usage_count"] == 1
    assert updated["success_count"] == 1

    # Log rejection
    rej_id = repo.log_rejection({
        "domain": "code_debugging",
        "subtask": "loop_bound_correction",
        "task_description": "fix loop",
        "code": "while True: pass",
        "reason": "Execution Timed Out",
        "created_in_session": "session_alpha"
    })
    rejections = repo.list_rejections()
    assert len(rejections) == 1
    assert rejections[0]["rejection_id"] == rej_id


def test_multi_session_sharing_and_data_isolation():
    """
    Core Abstract Requirement:
    Session Alpha synthesizes a skill.
    Session Beta can discover and reuse the validated skill, but cannot see Session Alpha's task data.
    """
    repo = get_repository()
    repo.reset_repository()
    lifecycle = get_lifecycle_engine()

    df_alpha = pd.DataFrame({"income": [3000.0, np.nan, 5000.0]})
    # Session Alpha runs task
    res_alpha = lifecycle.process_task(
        domain="tabular_cleaning",
        subtask="missing_value_imputation",
        task_name="Alpha Private Task",
        task_description="impute missing numeric values using median in dataframe",
        execution_args=[df_alpha],
        session_id="session_alpha"
    )
    assert res_alpha["lifecycle_status"] == "synthesized_and_validated"
    learned_skill_id = res_alpha["skill_id_used"]

    # Session Beta runs similar task: MUST REUSE Session Alpha's skill!
    df_beta = pd.DataFrame({"prices": [10.0, np.nan, 30.0]})
    res_beta = lifecycle.process_task(
        domain="tabular_cleaning",
        subtask="missing_value_imputation",
        task_name="Beta Task",
        task_description="impute missing numeric values using median in dataframe",
        execution_args=[df_beta],
        session_id="session_beta"
    )
    assert res_beta["lifecycle_status"] == "reused"
    assert res_beta["skill_id_used"] == learned_skill_id
    assert "REUSED_SKILL" in res_beta["badge"]
    assert res_beta["tokens_saved"] == 1200


def test_tabular_cleaning_domain_agent():
    """Verify full tabular cleaning pipeline produces cleaned data and diff report."""
    agent = get_tabular_agent()
    df = generate_sample_dirty_dataset("customer_churn")
    initial_nulls = df.isnull().sum().sum()

    res = agent.clean_dataset(df, session_id="test_tabular")
    assert res["success"] is True
    diff = res["diff_report"]
    assert diff["steps_executed"] >= 4
    assert diff["duplicates_removed"] >= 0
    assert len(res["cleaned_columns"]) == len(df.columns)


def test_code_debugging_domain_agent():
    """Verify code defect diagnosis, repair skill learning, and test verification."""
    agent = get_debugging_agent()
    bench = DEBUGGING_BENCHMARKS["off_by_one"]

    res = agent.debug_and_repair(
        buggy_code=bench["buggy_code"],
        entrypoint=bench["entrypoint"],
        test_cases=bench["failing_tests"],
        session_id="test_debug"
    )
    assert res["success"] is True
    assert res["repaired_code"] != ""
    assert len(res["verification_results"]) == len(bench["failing_tests"])
    assert all(v["passed"] for v in res["verification_results"])


def test_arbitrary_code_debugging_domains():
    """Verify debugging and repair of diverse arbitrary user code (recursion, palindrome, matrix, math)."""
    agent = get_debugging_agent()

    # 1. Recursive Factorial missing base case
    fact_code = "def factorial(n):\n    return n * factorial(n - 1)\n"
    res1 = agent.debug_and_repair(
        buggy_code=fact_code,
        entrypoint="factorial",
        test_cases=[{"inputs": [5], "expected": 120, "desc": "5! = 120"}, {"inputs": [1], "expected": 1, "desc": "1! = 1"}],
        session_id="custom_eval"
    )
    assert res1["success"] is True
    assert res1["classified_subtask"] == "recursion_base_case"
    assert all(v["passed"] for v in res1["verification_results"])

    # 2. Palindrome two-pointer out-of-bounds
    pal_code = "def is_palindrome(s):\n    if s is None: return True\n    left, right = 0, len(s)\n    while left < right:\n        if s[left] != s[right]: return False\n        left += 1; right -= 1\n    return True\n"
    res2 = agent.debug_and_repair(
        buggy_code=pal_code,
        entrypoint="is_palindrome",
        test_cases=[{"inputs": ["racecar"], "expected": True, "desc": "racecar is palindrome"}, {"inputs": ["hello"], "expected": False, "desc": "hello is not palindrome"}],
        session_id="custom_eval"
    )
    assert res2["success"] is True
    assert all(v["passed"] for v in res2["verification_results"])

    # 3. 2D Matrix Transpose index inversion
    mat_code = "def transpose_matrix(matrix):\n    if not matrix or not matrix[0]: return []\n    rows, cols = len(matrix), len(matrix[0])\n    transposed = []\n    for c in range(cols):\n        new_row = []\n        for r in range(rows):\n            new_row.append(matrix[c][r])\n        transposed.append(new_row)\n    return transposed\n"
    res3 = agent.debug_and_repair(
        buggy_code=mat_code,
        entrypoint="transpose_matrix",
        test_cases=[{"inputs": [[[1, 2, 3], [4, 5, 6]]], "expected": [[1, 4], [2, 5], [3, 6]], "desc": "Transpose 2x3"}],
        session_id="custom_eval"
    )
    assert res3["success"] is True
    assert all(v["passed"] for v in res3["verification_results"])

    # 4. Zero Division in Average Calculator with entrypoint auto-detection
    avg_code = "def calculate_average(numbers):\n    total = sum(numbers)\n    return total / len(numbers)\n"
    res4 = agent.debug_and_repair(
        buggy_code=avg_code,
        entrypoint=None, # Auto-detect!
        test_cases=[{"inputs": [[]], "expected": 0.0, "desc": "Empty list guard"}, {"inputs": [[10, 20, 30]], "expected": 20.0, "desc": "Average 20"}],
        session_id="custom_eval"
    )
    assert res4["success"] is True
    assert all(v["passed"] for v in res4["verification_results"])


def test_concrete_skills_notebook_example_ravi_priya():
    """
    Directly verifies the concrete pedagogical example:
    1. AI starts with notebook containing: remove_duplicates, fill_missing_values, detect_outliers, normalize_columns.
    2. User uploads CSV (Ravi, Priya, Arun with duplicates and missing age).
    3. User says "Clean this dataset" -> finds and reuses remove_duplicates & fill_missing_values.
    4. User asks "Convert every city name into uppercase" -> uppercase_city_names NOT FOUND.
    5. Agent synthesizes function, tests in sandbox on held-out cases (Test 1, 2, 3 PASS), promotes to repo.
    6. System gains uppercase_city_names as newly learned skill.
    7. Next time requested -> REUSED with 0 tokens and sub-15ms latency!
    """
    repo = get_repository()
    repo.seed_core_skills()
    agent = get_tabular_agent()

    # Step 1: Ensure notebook contains initial capabilities
    assert repo.search_skills("tabular_cleaning", "remove_duplicates: remove duplicate records in dataframe") is not None
    assert repo.search_skills("tabular_cleaning", "fill_missing_values: impute missing values in dataframe") is not None

    # Step 2: Load the exact student records dataset
    df = generate_sample_dirty_dataset("student_records")
    assert len(df) == 5
    assert df["Age"].isnull().sum() == 1
    assert df.duplicated().sum() == 1

    # Step 3: "Clean this dataset" -> Reuses existing validated skills
    res_clean = agent.clean_dataset(df, session_id="session_demo", instruction="Clean this dataset")
    assert res_clean["success"] is True
    cleaned_df = res_clean["cleaned_dataframe"]
    # Duplicates removed (5 -> 4 rows) and null age imputed
    assert len(cleaned_df) == 4
    age_col = [c for c in cleaned_df.columns if c.lower() == "age"][0]
    assert cleaned_df[age_col].isnull().sum() == 0
    # Confirm both steps were REUSED
    trace_clean = res_clean["pipeline_trace"]
    assert any(step["lifecycle_status"] == "reused" and "remove_duplicates" in step["subtask"] for step in trace_clean)
    assert any(step["lifecycle_status"] == "reused" and "fill_missing_values" in step["subtask"] for step in trace_clean)

    # Step 4 & 5: New Task: "Convert every city name into uppercase"
    # First verify it is NOT currently in repository
    repo_before = repo.search_skills("tabular_cleaning", "uppercase_city_names: convert every city name into uppercase")
    # If present from previous runs, delete it to verify the learning cycle
    if repo_before:
        with repo._get_connection() as conn:
            conn.cursor().execute("DELETE FROM skills WHERE subtask = 'uppercase_city_names'")
            conn.commit()

    assert repo.search_skills("tabular_cleaning", "uppercase_city_names: convert every city name into uppercase") is None

    # Execute instruction -> Triggers Discovery (NOT FOUND) -> Synthesize -> Sandbox Validate -> Promote
    res_upper = agent.clean_dataset(cleaned_df, session_id="session_demo", instruction="Convert every city name into uppercase")
    assert res_upper["success"] is True
    upper_df = res_upper["cleaned_dataframe"]

    # Verify City names are uppercase
    city_col = [c for c in upper_df.columns if c.lower() == "city"][0]
    assert list(upper_df[city_col]) == ["CHENNAI", "HYDERABAD", "BANGALORE", "HYDERABAD"]

    # Verify lifecycle trace shows newly learned and validated
    trace_upper = res_upper["pipeline_trace"]
    upper_step = [s for s in trace_upper if s["subtask"] == "uppercase_city_names"][0]
    assert upper_step["lifecycle_status"] == "synthesized_and_validated"
    assert "NEWLY_LEARNED" in upper_step["badge"]
    assert upper_step["validation_report"] is not None
    assert upper_step["validation_report"]["passed_cases"] == 3
    assert upper_step["validation_report"]["accuracy"] == 1.0

    # Step 6: Verify repository now contains newly learned uppercase_city_names
    newly_learned = repo.search_skills("tabular_cleaning", "uppercase_city_names: convert every city name into uppercase")
    assert newly_learned is not None
    assert newly_learned["validation_status"] == "validated"

    # Step 7: Second execution -> MUST REUSE the newly learned skill instantly!
    res_reuse = agent.clean_dataset(df, session_id="session_beta", instruction="Convert every city name into uppercase")
    assert res_reuse["success"] is True
    trace_reuse = res_reuse["pipeline_trace"]
    reuse_step = [s for s in trace_reuse if s["subtask"] == "uppercase_city_names"][0]
    assert reuse_step["lifecycle_status"] == "reused"
    assert "REUSED_SKILL" in reuse_step["badge"]
    assert reuse_step["tokens_saved"] == 1200
    assert reuse_step["latency_ms"] < 20.0