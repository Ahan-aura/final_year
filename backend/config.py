"""
Configuration module for Self-Evolving Agentic AI Workbench.
Batch A8-2 | Mohan Babu University, Tirupati
Base Paper: Pati, A. K. (2025). Agentic AI. IEEE Access.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# App Settings
PROJECT_NAME = "Self-Evolving Agentic AI Workbench"
VERSION = "1.0.0"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Storage Paths
if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    DATA_DIR = Path("/tmp/data")
    SCRATCH_DIR = Path("/tmp/scratch")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    # Copy seed databases if present in repository source
    import shutil
    source_skills = BASE_DIR / "data" / "skills_repository.db"
    dest_skills = DATA_DIR / "skills_repository.db"
    if source_skills.exists() and not dest_skills.exists():
        shutil.copy2(source_skills, dest_skills)

    source_metrics = BASE_DIR / "data" / "metrics_telemetry.db"
    dest_metrics = DATA_DIR / "metrics_telemetry.db"
    if source_metrics.exists() and not dest_metrics.exists():
        shutil.copy2(source_metrics, dest_metrics)
else:
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH_DIR = BASE_DIR / "scratch"
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

SKILLS_DB_PATH = DATA_DIR / "skills_repository.db"
METRICS_DB_PATH = DATA_DIR / "metrics_telemetry.db"

# Sandbox Safety Limits
SANDBOX_TIMEOUT_SECONDS = float(os.getenv("SANDBOX_TIMEOUT_SECONDS", 5.0))
MAX_EXECUTION_MEMORY_MB = int(os.getenv("MAX_EXECUTION_MEMORY_MB", 256))
MIN_VALIDATION_ACCURACY = 0.90  # 90% threshold to promote skill

# Semantic Search & Vector Settings
SIMILARITY_THRESHOLD = 0.70  # Cosine similarity threshold for skill reuse

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-flash-latest")
FALLBACK_TO_DETERMINISTIC = os.getenv("FALLBACK_TO_DETERMINISTIC_SYNTHESIZER", "false").lower() == "true"

# Sub-task Taxonomy
TABULAR_SUBTASKS = [
    "missing_value_imputation",
    "type_coercion",
    "duplicate_removal",
    "outlier_handling",
    "column_name_standardization",
    "date_parsing_normalization",
    "uppercase_city_names"
]

TAXONOMY_ALIASES = {
    "remove_duplicates": "duplicate_removal",
    "duplicate_removal": "remove_duplicates",
    "fill_missing_values": "missing_value_imputation",
    "missing_value_imputation": "fill_missing_values",
    "detect_outliers": "outlier_handling",
    "outlier_handling": "detect_outliers",
    "normalize_columns": "column_name_standardization",
    "column_name_standardization": "normalize_columns",
    "uppercase_cities": "uppercase_city_names",
    "uppercase_city_names": "uppercase_cities"
}

DEBUGGING_SUBTASKS = [
    "off_by_one_fix",
    "null_none_handling",
    "type_mismatch_fix",
    "loop_bound_correction",
    "operator_logic_fix",
    "missing_return_edge_case"
]

