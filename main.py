import os
import sys
from pathlib import Path

# Ensure root directory is on Python search path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

# Export app and handler for ASGI/WSGI serverless compatibility
handler = app
