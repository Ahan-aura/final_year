"""
FastAPI Server & REST API Gateway for the Self-Evolving Agentic AI Workbench.
Batch A8-2 | Mohan Babu University, Tirupati | Guide: Ms. Anusha Venkat N
Base Paper: Pati, A. K. (2025). Agentic AI. IEEE Access.
"""

import os
import io
import json
import ast
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import pandas as pd

from backend.config import PROJECT_NAME, VERSION, DATA_DIR
from backend.core.repository import get_repository
from backend.core.metrics_store import get_metrics_store
from backend.core.sandbox import get_sandbox
from backend.domains.tabular_cleaning import get_tabular_agent
from backend.domains.code_debugging import get_debugging_agent
from backend.datasets.tabular_benchmarks import generate_sample_dirty_dataset
from backend.datasets.debugging_benchmarks import DEBUGGING_BENCHMARKS
from backend.evaluation.benchmark_runner import get_benchmark_runner

app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="Self-Evolving Agentic AI Workbench for Autonomous Skill Learning and Adaptation"
)

# Enable CORS for frontend interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@app.on_event("startup")
def on_startup():
    """Initializes skill repository notebook with foundational skills."""
    get_repository().seed_core_skills()

# -------------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------------
class SessionRequest(BaseModel):
    session_id: str

class TabularTaskRequest(BaseModel):
    dataset_name: Optional[str] = "customer_churn"
    session_id: Optional[str] = "session_alpha"
    instruction: Optional[str] = "Clean this dataset"

class DebuggingTaskRequest(BaseModel):
    benchmark_key: Optional[str] = "off_by_one"
    custom_code: Optional[str] = None
    custom_entrypoint: Optional[str] = None
    custom_tests: Optional[List[Dict[str, Any]]] = None
    session_id: Optional[str] = "session_alpha"

class BenchmarkRequest(BaseModel):
    reset_first: Optional[bool] = False
    session_id: Optional[str] = "benchmark_eval_session"

# Active sessions tracker
ACTIVE_SESSIONS = set(["session_alpha", "session_beta", "session_eval"])

# -------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------
@app.get("/api/health")
def get_health():
    return {
        "status": "online",
        "project": PROJECT_NAME,
        "version": VERSION,
        "institution": "Mohan Babu University, Tirupati",
        "batch": "Batch A8-2",
        "guide": "Ms. Anusha Venkat N",
        "base_paper": "Pati, A. K. (2025). Agentic AI. IEEE Access.",
        "skills_count": len(get_repository().list_skills())
    }

@app.get("/api/sessions")
def list_sessions():
    return {"active_sessions": list(ACTIVE_SESSIONS)}

@app.post("/api/sessions")
def register_session(req: SessionRequest):
    ACTIVE_SESSIONS.add(req.session_id)
    return {"status": "ok", "session_id": req.session_id}

@app.get("/api/datasets")
def get_sample_datasets():
    """Returns available sample datasets and bug benchmarks."""
    return {
        "tabular_datasets": [
            {
                "id": "student_records",
                "name": "Student Records (Ravi & Priya - Chennai, Hyderabad, Bangalore)",
                "description": "Concrete example: duplicate Ravi records, missing Priya age, mixed cities (Chennai, Hyderabad, Bangalore)."
            },
            {
                "id": "customer_churn",
                "name": "Customer Churn Telecom Dataset",
                "description": "32 rows with missing tenures, uncoerced charges ($), duplicate customer IDs, and unformatted dates."
            },
            {
                "id": "healthcare",
                "name": "Healthcare Patient Vitals Dataset",
                "description": "27 rows with missing blood pressures, negative ages, dirty column headers, and extreme cholesterol outliers."
            },
            {
                "id": "ecommerce",
                "name": "E-Commerce Online Orders Dataset",
                "description": "27 rows with messy dates, uncleaned dollar prices ($1,250.00), percentages, and missing customer names."
            }
        ],
        "debugging_benchmarks": [
            {
                "id": k,
                "name": v["title"],
                "subtask": v["subtask"],
                "description": v["description"],
                "failing_tests_count": len(v["failing_tests"])
            }
            for k, v in DEBUGGING_BENCHMARKS.items()
        ]
    }

@app.post("/api/tabular/clean")
def clean_tabular_data(req: TabularTaskRequest):
    """Executes tabular cleaning agent on pre-built or sample datasets."""
    ACTIVE_SESSIONS.add(req.session_id)
    agent = get_tabular_agent()
    try:
        df = generate_sample_dirty_dataset(req.dataset_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid dataset: {str(e)}")

    try:
        res = agent.clean_dataset(df, session_id=req.session_id, instruction=req.instruction)
        return {
            "dataset_name": req.dataset_name,
            "session_id": req.session_id,
            "instruction": req.instruction,
            "diff_report": res["diff_report"],
            "pipeline_trace": res["pipeline_trace"],
            "initial_profile": res["initial_profile"],
            "final_profile": res["final_profile"],
            "sample_cleaned_rows": res["cleaned_records"][:15],
            "columns": res["cleaned_columns"],
            "cleaned_csv_text": res["cleaned_dataframe"].to_csv(index=False),
            "total_rows": len(res["cleaned_dataframe"])
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tabular pipeline error: {str(e)}")

class UploadCsvRequest(BaseModel):
    csv_text: str
    filename: Optional[str] = "uploaded_data.csv"
    session_id: Optional[str] = "session_alpha"
    instruction: Optional[str] = "Clean this dataset"

@app.post("/api/tabular/upload")
def upload_csv_and_clean(req: UploadCsvRequest):
    """Allows user to upload/paste their own dirty CSV text for live cleaning."""
    ACTIVE_SESSIONS.add(req.session_id)
    try:
        df = pd.read_csv(io.StringIO(req.csv_text))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    agent = get_tabular_agent()
    try:
        res = agent.clean_dataset(df, session_id=req.session_id, instruction=req.instruction)
        return {
            "dataset_name": req.filename,
            "session_id": req.session_id,
            "instruction": req.instruction,
            "diff_report": res["diff_report"],
            "pipeline_trace": res["pipeline_trace"],
            "initial_profile": res["initial_profile"],
            "final_profile": res["final_profile"],
            "sample_cleaned_rows": res["cleaned_records"][:15],
            "columns": res["cleaned_columns"],
            "cleaned_csv_text": res["cleaned_dataframe"].to_csv(index=False),
            "total_rows": len(res["cleaned_dataframe"])
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tabular pipeline error: {str(e)}")

class InspectCodeRequest(BaseModel):
    code: str

@app.post("/api/debugging/inspect")
def inspect_code(req: InspectCodeRequest):
    """Analyzes custom code AST to detect entrypoint function and parameters."""
    code = req.code.strip()
    entrypoint = None
    params = []
    docstring = None
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                entrypoint = node.name
                params = [arg.arg for arg in node.args.args]
                docstring = ast.get_docstring(node)
                break
    except Exception as e:
        return {"success": False, "error": str(e), "entrypoint": None, "params": []}

    return {
        "success": True,
        "entrypoint": entrypoint or "solution",
        "params": params,
        "docstring": docstring,
        "sample_tests": [
            {"inputs": [1] * len(params) if params else [], "expected": None, "desc": f"Smoke test for {entrypoint or 'function'}"}
        ]
    }

@app.post("/api/debugging/repair")
def repair_code_defect(req: DebuggingTaskRequest):
    """Diagnoses, learns/reuses repair skill, and verifies fix."""
    ACTIVE_SESSIONS.add(req.session_id)
    agent = get_debugging_agent()

    if req.custom_code and req.custom_code.strip():
        buggy_code = req.custom_code
        entrypoint = req.custom_entrypoint
        test_cases = req.custom_tests or []
    else:
        bench = DEBUGGING_BENCHMARKS.get(req.benchmark_key)
        if not bench:
            raise HTTPException(status_code=404, detail="Benchmark not found")
        buggy_code = bench["buggy_code"]
        entrypoint = bench["entrypoint"]
        test_cases = bench["failing_tests"]

    res = agent.debug_and_repair(
        buggy_code=buggy_code,
        entrypoint=entrypoint,
        test_cases=test_cases,
        session_id=req.session_id
    )
    return res

@app.get("/api/skills")
def get_skills(domain: Optional[str] = None):
    """Retrieves all validated skills stored in the repository."""
    repo = get_repository()
    return {"skills": repo.list_skills(domain=domain)}

@app.get("/api/skills/{skill_id}")
def get_single_skill(skill_id: str):
    repo = get_repository()
    skill = repo.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill

@app.post("/api/skills/{skill_id}/test")
def test_skill_in_sandbox(skill_id: str):
    """Ad-hoc sandbox execution of a validated skill."""
    repo = get_repository()
    skill = repo.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    sandbox = get_sandbox()
    test_cases = skill.get("test_cases", [])
    if not test_cases:
        return {"status": "no_test_cases", "message": "Skill has no recorded test cases"}

    val_report = sandbox.validate_skill(
        code_str=skill["code"],
        entrypoint=skill["entrypoint"],
        held_out_test_cases=test_cases
    )
    return val_report.to_dict()

@app.get("/api/rejections")
def get_rejections():
    """Lists skills rejected by the sandbox validation gate."""
    repo = get_repository()
    return {"rejections": repo.list_rejections()}

@app.get("/api/metrics/dashboard")
def get_dashboard_metrics():
    """Returns real-time aggregated metrics and growth curve time series."""
    metrics_store = get_metrics_store()
    return metrics_store.get_aggregated_dashboard_metrics()

@app.post("/api/benchmark/run")
def run_benchmark(req: BenchmarkRequest):
    """Executes sequential 10-task benchmark and returns step-by-step evolution data."""
    runner = get_benchmark_runner()
    return runner.run_benchmark_suite(
        reset_first=bool(req.reset_first),
        session_id=req.session_id or "benchmark_eval_session"
    )

@app.post("/api/repository/reset")
def reset_all_data():
    """Clears repository and metrics for clean demo presentation."""
    get_repository().reset_repository()
    get_metrics_store().reset_metrics()
    return {"status": "reset_completed", "message": "Skill repository and telemetry reset."}

# Mount static frontend assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_frontend():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Frontend not found, please build frontend/index.html"}