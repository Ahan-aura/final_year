import os
import sys
from pathlib import Path

# Add project root and current dir to sys.path so 'backend' can be resolved by Vercel serverless runtime
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from backend.main import app
    handler = app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import traceback
    
    app = FastAPI(title="Vercel Diagnostic Handler")
    err_trace = traceback.format_exc()

    @app.get("/")
    @app.get("/{path_name:path}")
    def debug_route(path_name: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "FastAPI initialization failed on Vercel runtime",
                "exception": str(e),
                "traceback": err_trace,
                "sys_path": sys.path,
                "root_files": os.listdir(str(ROOT_DIR)) if ROOT_DIR.exists() else []
            }
        )
    handler = app
