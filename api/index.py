import os
import sys
from pathlib import Path

# Add project root to sys.path so 'backend' is resolved
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app as fastapi_app

# Top-level exports required by Vercel's Python AST parser
app = fastapi_app
handler = app
application = app
