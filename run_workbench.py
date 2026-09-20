"""
Single-Command Launcher for Self-Evolving Agentic AI Workbench.
Batch A8-2 | Mohan Babu University, Tirupati | Guide: Ms. Anusha Venkat N
Base Paper: Pati, A. K. (2025). Agentic AI: A Comprehensive Survey. IEEE Access.
"""

import sys
import os
import webbrowser
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import uvicorn
from backend.config import HOST, PORT, PROJECT_NAME, VERSION

def print_banner():
    banner = f"""
================================================================================
          {PROJECT_NAME.upper()}
                     Version {VERSION} | Capstone Project
   Batch A8-2 | Mohan Babu University, Tirupati | Guide: Ms. Anusha Venkat N
   Base Paper: Pati, A. K. (2025). Agentic AI. IEEE Access, 13, 151824-151837
================================================================================
[+] Architecture: 6-Stage Skill Lifecycle (Discover -> Synthesize -> Validate -> Execute -> Evaluate -> Promote)
[+] Domains: 1) Automated Tabular Cleaning  2) Automated Code Debugging
[+] Sandbox: AST Security Guard + Timeout + Held-Out Unit Test Suites
[+] Storage: Persistent SQLite Skill Repository + Metrics Store
[+] Server URL: http://{HOST}:{PORT}
================================================================================
"""
    print(banner)

def main():
    print_banner()
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()