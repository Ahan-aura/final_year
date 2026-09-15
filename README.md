# Self-Evolving Agentic AI Workbench for Autonomous Skill Learning and Adaptation

**Batch No:** A8-2 | **Institution:** Department of Computer Science & Engineering, Mohan Babu University, Tirupati  
**Project Guide:** Ms. Anusha Venkat N, Assistant Professor  
**Student Team:**  
- Edamakanti Ranga Pravallika (23102A040606)  
- Penubala Ashritha (23102A040623)  
- Eftekarul Mullick (23102A040600)  
- Dronadula Kasi (23102A040565)  

**Base Paper:**  
Pati, A. K. (2025). *Agentic AI: A Comprehensive Survey of Technologies, Applications, and Societal Implications.* IEEE Access, 13, 151824–151837. [DOI: 10.1109/ACCESS.2025.3585609](https://ieeexplore.ieee.org/document/11071266)

---

## 1. Executive Summary & Abstract

Traditional agentic AI frameworks treat agent capabilities as static after deployment: each task triggers a costly, redundant LLM generation, or relies on hardcoded prompts without systematic adaptation. 

This workbench establishes an **autonomous 6-stage skill lifecycle**:
$$\text{Discover} \longrightarrow \text{Synthesize} \longrightarrow \text{Validate (Sandbox)} \longrightarrow \text{Execute} \longrightarrow \text{Evaluate} \longrightarrow \text{Promote / Reuse}$$

Operating across two foundational applied domains:
1. **Automated Tabular Data Cleaning** (missing value imputation, type coercion, deduplication, outlier clipping, header standardization, date parsing).
2. **Automated Code Debugging** (off-by-one boundary fixes, null/None exceptions, type mismatches, loop termination, logic inversions, zero-division edge cases).

The agent first searches a **shared SQLite skill repository** using dense semantic vector similarity ($>0.70$ threshold). If no validated skill exists, the system synthesizes executable Python code, submits it to a **secure sandboxed execution environment** equipped with **AST security inspection**, tests it against **held-out test cases**, and only promotes it if it passes $\ge 90\%$ without security violations.

A **live Web UI and Dashboard** provides real-time observability over the **learning curve**: as the skill repository fills, latency drops by **over 95%** (from $\sim2,000\,\text{ms}$ down to $<10\,\text{ms}$) and token consumption drops to zero on reuse.

---

## 2. System Architecture

```
                               ┌────────────────────────────────┐
                               │     Modern Web Interface       │
                               │  (Playground, Repo, Analytics) │
                               └───────────────┬────────────────┘
                                               │
                               ┌───────────────▼────────────────┐
                               │      FastAPI Gateway &         │
                               │   Multi-Session Orchestrator   │
                               └───┬────────────────────────┬───┘
                                   │                        │
                    ┌──────────────▼───┐        ┌───────────▼──────────┐
                    │  Domain Agent 1  │        │   Domain Agent 2     │
                    │ Tabular Cleaning │        │   Code Debugging     │
                    └──────────┬───────┘        └───────────┬──────────┘
                               │                            │
                               └───────────────┬────────────┘
                                               │
                          ┌────────────────────▼───────────────────┐
                          │         Skill Lifecycle Engine         │
                          │ 1. Discover (Embedding Cosine Search)  │
                          │ 2. Synthesize (LLM Code Generation)    │
                          │ 3. Validate (Sandbox + Held-Out Tests) │
                          │ 4. Execute (Target Task Execution)     │
                          │ 5. Evaluate (Telemetry & Latency Log)  │
                          │ 6. Promote / Reuse (Shared Repository) │
                          └────────────────────┬───────────────────┘
                                               │
                     ┌─────────────────────────┴─────────────────────────┐
                     │                                                   │
          ┌──────────▼──────────┐                             ┌──────────▼──────────┐
          │ Safe Execution      │                             │ Shared Skill        │
          │ Sandbox Gate        │                             │ Repository (SQLite) │
          │ - AST Inspection    │                             │ - Dense Vectors     │
          │ - 5s Timeout Cap    │                             │ - Visibility Scopes │
          │ - Held-Out Cases    │                             │ - Rejections Log    │
          └─────────────────────┘                             └─────────────────────┘
```

---

## 3. Key Research Claims & Novelty

| Dimension | Standard Agentic Frameworks | Our Self-Evolving Workbench |
|---|---|---|
| **Skill Adaptability** | Static prompt engineering | Autonomous synthesis and repository promotion |
| **Execution Safety** | Direct unvalidated execution | AST Security Guard blocks forbidden calls (`os`, `subprocess`, `eval`) |
| **Validation Rigor** | Self-generated or zero validation | Evaluated against private held-out test suites in sandbox |
| **Observability** | Hidden terminal logs | Live web charts tracking reuse rate, latency curve, and ablation |
| **Multi-Session** | Single session memory | Validated skills shared across sessions; private task data strictly isolated |

---

## 4. Quickstart Guide

### Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome, Edge, Firefox)

### Installation
```bash
# Clone the repository
git clone https://github.com/Ahan-aura/final_year.git
cd final_year

# (Optional) Create and activate virtual environment
python -m venv venv
# On Windows: venv\Scripts\activate
# On Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

### Run the Application
```bash
python run_workbench.py
```
Open your browser to: **`http://127.0.0.1:8000`**

### Run the Automated Test Suite
```bash
pytest backend/tests/test_all_components.py -v
```
*(All 8 comprehensive tests pass 100%)*

---

## 5. Live Demonstration Script for Evaluators

1. **Step 1: Open the Workbench Playground (`http://127.0.0.1:8000`)**
   - Note the top header showing **Batch A8-2**, Mohan Babu University, and active session `session_alpha`.
2. **Step 2: Run Tabular Cleaning (Task 1)**
   - Select *Customer Churn Telecom* dataset and click **"Clean with Agent"**.
   - Notice the badge: `🆕 LEARNED & VALIDATED`. The system synthesizes the cleaning pipeline, passes the sandbox validation gate, and stores the skills.
3. **Step 3: Switch to Session Beta & Demonstrate Instant Reuse (Task 2)**
   - Change the session selector to `session_beta`.
   - Run the tabular cleaning pipeline again.
   - Watch the badge turn to **`✅ REUSED_SKILL`**! Latency drops to **$<15\,\text{ms}$** and token consumption drops to zero.
4. **Step 4: Run Code Debugging**
   - Click the **"Domain 2: Code Debugging"** tab.
   - Select *Binary Search Loop Boundary (Off-by-one)* and click **"Diagnose & Repair with Agent"**.
   - Inspect the unified code diff and verify that all sandbox verification unit tests pass.
5. **Step 5: View the Evolution Analytics Dashboard**
   - Navigate to the **"Evolution Analytics"** tab.
   - Inspect the 4 real-time graphs showing the learning curve, latency drop, and ablation comparison against the Direct LLM Baseline.
6. **Step 6: Run the 10-Task Capstone Benchmark**
   - Click **"Sequential Benchmark"** &rarr; **"Run 10-Task Capstone Suite"**.
   - Watch tasks 4, 6, 7, 9, 10 seamlessly reuse earlier skills in real time!