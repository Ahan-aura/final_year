# System Architecture & Academic Specification
## Self-Evolving Agentic AI Workbench for Autonomous Skill Learning and Adaptation
**Batch No:** A8-2 | **Mohan Babu University, Tirupati** | **Guide:** Ms. Anusha Venkat N  
**Base Paper:** Pati, A. K. (2025). *Agentic AI: A Comprehensive Survey of Technologies, Applications, and Societal Implications.* IEEE Access.

---

## 1. Grounding in the Base Paper (Pati, 2025)

The IEEE Access survey by Ashis Kumar Pati provides a formal taxonomy of agentic architectures. Our capstone project directly operationalizes and extends key foundations identified in the survey:

1. **Operationalizing "Learning Agents" & "Meta-Reasoning Agents" (Section III-C)**:
   - Pati (2025) categorizes AI agents into Reflex, Goal-Based, Utility-Based, Learning, and Meta-Reasoning agents.
   - Most existing systems operate merely as Reflex or Goal-Based agents with static prompts.
   - Our system implements a true **Learning and Meta-Reasoning Agent**: it inspects failures, synthesizes parameterized functions, checks correctness in a sandbox, and meta-reasons over its own repository of accumulated knowledge.

2. **Resolving the Evaluation & Interpretability Gap (Sections IV-B-3 and VII-A)**:
   - The survey identifies a major limitation in modern agentic AI: agent adaptability is often evaluated through non-reproducible, proprietary benchmarks where internal learning steps cannot be observed.
   - Our workbench makes skill discovery, validation, and reuse **observable, auditable, and quantifiable** through a unified telemetry dashboard and a transparent SQLite repository.

---

## 2. The 6-Stage Skill Lifecycle

```
[1. DISCOVER]  --> Query embedding similarity in Shared Repository (>0.70 threshold)
       |
       +--> If Found: [4. EXECUTE (REUSED)] -> [5. EVALUATE] -> [6. LOG REUSE METRICS]
       |
       +--> If Not Found:
                 |
           [2. SYNTHESIZE]  --> LLM generates executable Python code with strict I/O schema
                 |
           [3. VALIDATE]    --> AST Security Guard checks imports & dunder methods
                 |          --> Run against private Held-Out Test Suite in Sandbox
                 |          --> If passed (>=90% accuracy):
                 |                 [6. PROMOTE TO SHARED REPO]
                 |              Else:
                 |                 [LOG REJECTION & RETRY/FALLBACK]
                 |
           [4. EXECUTE]     --> Run promoted function on actual user task input
                 |
           [5. EVALUATE]    --> Record latency, tokens saved, and statistical diffs
```

---

## 3. Sub-Task Taxonomy

### Domain 1: Automated Tabular Data Cleaning
1. `missing_value_imputation`: Dynamic numeric median imputation and categorical mode substitution.
2. `type_coercion`: Stripping currency symbols (`$`, `€`, `£`), commas, percentages, and parsing string numbers to IEEE floats.
3. `duplicate_removal`: Deduplication of exact and subset row signatures with index resetting.
4. `outlier_handling`: Empirical Interquartile Range (IQR) fence detection ($[Q_1 - 1.5 \times \text{IQR}, Q_3 + 1.5 \times \text{IQR}]$) and boundary clipping.
5. `column_name_standardization`: Lowercased, whitespace-trimmed, snake_case normalization with special character elimination.
6. `date_parsing_normalization`: Parsing heterogeneous date formats (`YYYY/MM/DD`, `DD-MM-YYYY`) into ISO-8601 standard (`YYYY-MM-DD`).

### Domain 2: Automated Code Debugging
1. `off_by_one_fix`: Off-by-one boundary correction in array indexing, search bounds, and slice ranges.
2. `null_none_handling`: Defensive attribute and nested dictionary retrieval against `NoneType` and missing keys.
3. `type_mismatch_fix`: Type coercion handling string-number concatenations and formatting.
4. `loop_bound_correction`: Counter advancement and loop termination condition corrections to prevent infinite execution.
5. `operator_logic_fix`: Correction of inverted logical operators (`and` vs `or`, `==` vs `!=`).
6. `missing_return_edge_case`: Boundary edge case handling, zero-division guards, and default return path enforcement.

---

## 4. Sandbox Security Model & AST Inspection

To guarantee that autonomous code synthesis cannot compromise the host environment, the sandbox enforces a strict multi-layer defense:

```python
# Prohibited Modules
FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
    "http", "ftplib", "importlib", "posix", "nt", "pty", "commands",
    "threading", "multiprocessing", "ctypes", "inspect", "builtins"
}

# Prohibited Calls & Dunders
FORBIDDEN_CALLS = {"eval", "exec", "compile", "globals", "locals", "getattr", "setattr", "delattr"}
FORBIDDEN_ATTRIBUTES = {"__subclasses__", "__bases__", "__mro__", "__globals__", "__code__", "__builtins__"}
```

1. **AST Node Inspection**: Before execution, `ast.parse()` parses the code tree. Any node referencing forbidden modules, functions, or dunders triggers an immediate rejection.
2. **Restricted Execution Namespace**: Execution occurs in an isolated dictionary containing only pure Python primitives and authorized libraries (`pandas`, `numpy`, `math`, `re`, `datetime`, `json`).
3. **Execution Timeout**: Enforced via `concurrent.futures.ThreadPoolExecutor` with a strict timeout limit (e.g. 5.0 seconds).
4. **Held-Out Validation Gate**: Skills are executed on held-out test cases not visible to the synthesizer. Promotion requires $\ge 90\%$ test accuracy.

---

## 5. Multi-Session Isolation Model

- **Shared Repository Layer**:
  - Validated skills are stored with `visibility: shared`.
  - Any session (e.g. `session_beta`) can discover and reuse skills learned by prior sessions (`session_alpha`).
- **Isolated Session Layer**:
  - Raw datasets, uploaded CSVs, user parameters, and execution task logs are partitioned by `session_id`.
  - Session Beta cannot query or view Session Alpha's proprietary task data.