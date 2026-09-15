# Self-Evolving Agentic AI Workbench — End-to-End Project Plan
### Batch A8-2 | Mohan Babu University | Guide: Ms. Anusha Venkat N

---

## 1. What You're Actually Building (in one paragraph)

An agentic system where, for a task in either of two domains — **tabular data cleaning** and **code debugging** — the agent first checks a **shared skill repository** for a validated reusable function. If none exists, it **synthesizes** one (an LLM writes executable code for the sub-task), **tests it in a sandbox** on held-out cases, and only **promotes** it to the repository if it passes. A **web UI** shows, per task, whether a skill was *reused* or *newly learned*, and a **dashboard** tracks success rate, execution cost, and reuse frequency over time — so you can literally show a graph where performance improves as the skill library grows. That growth curve is your headline result.

---

## 2. System Architecture

```
                        ┌─────────────────────────┐
                        │        Web UI            │
                        │  (submit task, see       │
                        │   reused/learned status, │
                        │   dashboard)              │
                        └────────────┬─────────────┘
                                     │
                        ┌────────────▼─────────────┐
                        │      Orchestrator         │
                        │  (task router + session   │
                        │   manager)                │
                        └───┬───────────────────┬───┘
                             │                   │
              ┌──────────────▼───┐   ┌───────────▼──────────┐
              │  Domain Agent 1    │   │  Domain Agent 2       │
              │  Tabular Cleaning  │   │  Code Debugging       │
              └──────────┬─────────┘   └───────────┬──────────┘
                          │                          │
                          └────────────┬─────────────┘
                                       │
                     ┌─────────────────▼──────────────────┐
                     │        Skill Lifecycle Engine        │
                     │  1. Search repo (embedding/keyword)  │
                     │  2. Synthesize (LLM → code)          │
                     │  3. Validate (sandbox, held-out set) │
                     │  4. Execute (on real task)           │
                     │  5. Evaluate (log outcome/cost)      │
                     │  6. Promote/Reuse (write to repo)    │
                     └─────────────────┬─────────────────────┘
                                       │
                     ┌─────────────────▼──────────────────┐
                     │     Shared Skill Repository (DB)     │
                     │  skill_id, domain, description,      │
                     │  embedding, code, test_cases,        │
                     │  validation_status, success_count,   │
                     │  avg_cost, created_by_session        │
                     └───────────────────────────────────────┘
                                       │
                     ┌─────────────────▼──────────────────┐
                     │   Metrics Store + Dashboard Backend   │
                     │  per-task logs → aggregated charts    │
                     └───────────────────────────────────────┘
```

Key design decision baked into your abstract: **skills are shared across sessions, but task data is isolated per session.** So the repository table needs a `visibility: shared` flag while task logs/data are scoped by `session_id`.

---

## 3. Recommended Tech Stack

| Layer | Choice | Why |
|---|---|---|
| LLM for synthesis/reasoning | Claude or GPT-4-class API (pick one, keep consistent for reproducibility) | Needs strong code generation + tool use |
| Sandboxed execution | Docker container or `subprocess` with resource/time limits, or a restricted Python exec with `RestrictedPython` | You **must** isolate execution — this is a grading/safety point, not optional |
| Skill repository | PostgreSQL (or SQLite for simplicity) + pgvector or FAISS for embedding search | Lets you do "search for a similar skill" semantically, not just exact match |
| Backend/orchestration | Python (FastAPI) | Easiest to wire LLM calls + sandbox + DB together |
| Web UI | React (or plain HTML/JS if time-constrained) | Needs to show reused-vs-learned badge + dashboard |
| Dashboard | Recharts / Plotly / Chart.js | Live plots of success rate, cost, reuse frequency |
| Domain 1 test data | Kaggle "messy" datasets (e.g. dirty CSVs with missing values, inconsistent types, duplicates) | Public, easy to construct held-out cases |
| Domain 2 test data | Small buggy code snippets — use existing bug-injection datasets (e.g. QuixBugs, Defects4J subset) or hand-craft 30–50 bugs | Gives you a controlled ground truth for "did it actually fix it" |

---

## 4. The Skill Object — Design This Early

Every skill in the repository should be a structured record, not just a code blob:

```json
{
  "skill_id": "uuid",
  "domain": "tabular_cleaning | code_debugging",
  "task_description": "natural language description of what sub-task this solves",
  "embedding": [ ... ],
  "code": "def clean_missing_numeric(df, col): ...",
  "input_schema": "...",
  "output_schema": "...",
  "test_cases": [ {"input": ..., "expected": ...}, ... ],
  "validation_status": "validated | rejected | pending",
  "validation_accuracy": 0.93,
  "usage_count": 12,
  "success_rate": 0.91,
  "avg_execution_cost_ms": 45,
  "created_at": "...",
  "created_in_session": "..."
}
```

Getting this schema right on day one saves you weeks — the dashboard, the reuse logic, and the report all read from this.

---

## 5. Phase-by-Phase Plan (12–14 week timeline)

### Phase 0 — Setup & Scoping (Week 1)
- Finalize exact sub-task taxonomy for each domain (don't leave "tabular cleaning" vague). Suggested sub-tasks:
  - *Tabular*: missing value imputation, type coercion, duplicate removal, outlier handling, column name standardization, date parsing.
  - *Debugging*: off-by-one errors, null/None handling, type mismatches, incorrect loop bounds, wrong operator (== vs =, and vs or), missing return statements.
- Set up repo, environments, API keys, sandbox container.
- Write a one-page technical design doc (this becomes your report's Chapter 3 draft).

### Phase 1 — Skill Repository + Discovery (Weeks 2–3)
- Build DB schema above.
- Implement **discovery**: given an incoming task, embed its description and search repository for a semantically similar validated skill (cosine similarity threshold, e.g. >0.85).
- Unit test: manually seed 3–4 skills, confirm discovery correctly finds/rejects matches.

### Phase 2 — Synthesis (Weeks 3–4)
- When no skill is found, prompt the LLM to generate an executable Python function for the sub-task, with a strict I/O contract (e.g. "takes a pandas DataFrame and column name, returns cleaned DataFrame").
- Force structured output (function code + docstring + example test cases the LLM itself proposes).

### Phase 3 — Sandboxed Validation (Weeks 4–5) — **this is your novelty claim, invest here**
- Run the synthesized function against **held-out test cases** you control (not just the LLM's self-generated ones).
- Define a pass threshold (e.g. ≥90% of held-out cases correct, no exceptions, executes within time/memory limit).
- Only if it passes → promote to repository with `validation_status: validated`.
- If it fails → log the failure, optionally retry synthesis once with the failure feedback, otherwise mark `rejected` and fall back to a default/naive method.
- **This is the part reviewers will grill you on** — be ready to explain exactly what "safe" and "sandboxed" mean in your implementation (resource limits, no network access, no file system access outside a scratch dir).

### Phase 4 — Execution & Domain Agents (Weeks 5–7)
- Wire the two domain agents to call the lifecycle engine.
- Domain Agent 1 (tabular): takes a messy CSV, plans a sequence of cleaning sub-tasks, applies skill for each, outputs cleaned CSV + a diff report.
- Domain Agent 2 (debugging): takes buggy code + failing test, plans diagnosis, applies/synthesizes a fix skill, re-runs tests to confirm fix.
- Log every step: which skill was used, reused vs. new, execution time, success/failure.

### Phase 5 — Web Interface (Weeks 7–9)
- Task submission page (upload CSV / paste buggy code).
- Result page showing: per-step trace, "✅ Reused skill #X" or "🆕 Learned new skill", before/after diff.
- This is what you'll demo live — make it visually clean, not just functional.

### Phase 6 — Live Dashboard (Weeks 8–9, parallel with Phase 5)
- Charts: success rate over time, execution cost over time, % of tasks using reused vs. newly-synthesized skills, skill repository growth curve.
- This dashboard **is your experimental results section** — design it so a screenshot tells the whole story of "system gets better as it accumulates skills."

### Phase 7 — Multi-Session Sharing (Week 9–10)
- Implement session isolation for task data, shared visibility for validated skills.
- Test: run two "users"/sessions, confirm session 2 can reuse a skill session 1 validated, but cannot see session 1's raw task data.

### Phase 8 — Evaluation Experiments (Weeks 10–11) — **do this before writing the report**
Design a proper before/after comparison, not just "it works":
- Run N tasks (e.g. 50 tabular cleaning jobs, 50 debugging jobs) in order.
- Plot success rate and cost in batches of 10 tasks — you want to show the curve improving as the skill library fills up (fewer synthesis calls, higher success rate, lower cost per task later in the run).
- Compare against a **baseline**: same tasks solved by direct LLM call each time with *no* skill reuse (this is your ablation — critical for showing your contribution isn't "just an LLM call").
- Compute: success rate, average cost (tokens/time), reuse frequency, skill promotion rate (validated vs rejected).

### Phase 9 — Documentation, Report & Paper Alignment (Weeks 11–13)
- Map every claim in your abstract to a concrete result: "prevents unreliable skills from propagating" → show a table of rejected skills and why.
- Explicitly connect back to the base paper (Pati, 2025) — your system operationalizes the paper's "learning agents" and "meta-reasoning agents" categories (Section III-C) and directly addresses the paper's identified gap around **interpretability and evaluation metrics** (Section IV-B-3, VII-A) by making skill reuse/validation observable and measurable. Cite this explicitly in your Related Work / Motivation.
- Write chapters: Introduction, Literature Survey (extend the base paper's Table 3 comparison to include your system as a row), System Design, Implementation, Results, Conclusion & Future Work.

### Phase 10 — Demo Prep & Viva (Week 13–14)
- Prepare a **live demo script**: one tabular task that reuses an existing skill, one that triggers new synthesis+validation (so evaluators see both paths).
- Prepare answers for likely questions (see Section 7 below).
- Rehearse the dashboard walkthrough — this is your strongest visual asset.

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM-synthesized code is unsafe/unreliable | Sandbox with strict timeouts, no filesystem/network access, resource caps; validation gate before promotion |
| "Improvement over time" curve doesn't show clearly | Curate your test task sequence deliberately — include some tasks that are variations of earlier ones so reuse actually triggers |
| Scope creep (trying to support too many sub-task types) | Lock the sub-task taxonomy in Phase 0 and don't add more mid-project |
| Running out of time for the report | Start report chapters (System Design, Related Work) in parallel with Phase 3–4, don't wait until the end |
| Evaluators ask "how is this different from just calling an LLM each time?" | Have the baseline ablation (Phase 8) ready — this is your strongest defense |

---

## 7. Likely Viva/Evaluation Questions to Prepare For

1. How do you guarantee a "validated" skill is actually safe to reuse on new inputs it wasn't tested on?
2. What happens if a validated skill starts failing later (skill drift)? Do you re-validate periodically?
3. How is your skill discovery different from just caching LLM responses?
4. What's your sandbox actually isolating against — malicious code, or just bugs?
5. How do you decide when to trust an existing skill vs. re-synthesize?
6. Why these two domains specifically — what's the argument they generalize?

---

## 8. Immediate Next Steps (this week)

1. Lock the sub-task taxonomy (Section 5, Phase 0).
2. Set up repo structure and pick your LLM API + sandbox approach.
3. Design and finalize the skill schema (Section 4) — don't skip this, it anchors everything downstream.
4. Collect/construct your held-out test datasets for both domains now, since Phase 3 validation depends on them.

---

*This plan is designed so that by Week 9 you have a working system, leaving weeks 10–14 purely for evaluation, writing, and polish — the phase most capstone teams underestimate.*
