"""
Sandboxed Execution & Validation Engine.
Provides AST security analysis, isolated execution environments,
timeout enforcement, and held-out test case evaluation.
"""

import ast
import time
import sys
import io
import copy
import traceback
import math
import re
import datetime
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Dict, Any, List, Optional, Tuple, Callable
import pandas as pd
import numpy as np

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests",
    "http", "ftplib", "importlib", "posix", "nt", "pty", "commands",
    "threading", "multiprocessing", "ctypes", "inspect", "builtins"
}

ALLOWED_IMPORT_MODULES = {
    "pandas", "numpy", "math", "re", "datetime", "json", "time"
}

FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "globals", "locals",
    "getattr", "setattr", "delattr"
}

FORBIDDEN_ATTRIBUTES = {
    "__subclasses__", "__bases__", "__mro__", "__globals__", "__code__",
    "__builtins__", "__class__"
}

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Guarded import function for the sandbox execution namespace."""
    base_mod = name.split(".")[0]
    if base_mod in FORBIDDEN_MODULES or base_mod not in ALLOWED_IMPORT_MODULES:
        raise ImportError(f"Importing '{name}' is strictly prohibited in execution sandbox.")
    import builtins
    return getattr(builtins, "__import__")(name, globals, locals, fromlist, level)

SAFE_BUILTINS = {
    "__import__": _safe_import,
    "range": range, "len": len, "int": int, "float": float, "str": str,
    "list": list, "dict": dict, "set": set, "tuple": tuple, "bool": bool,
    "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
    "enumerate": enumerate, "zip": zip, "sorted": sorted, "any": any,
    "all": all, "isinstance": isinstance, "issubclass": issubclass,
    "print": print, "map": map, "filter": filter,
    # Standard Exceptions
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError, "ZeroDivisionError": ZeroDivisionError,
    "AttributeError": AttributeError, "ImportError": ImportError
}

class ASTSecurityGuard(ast.NodeVisitor):
    """Inspects AST of synthesized code to guarantee safety before execution."""

    def __init__(self):
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            if base_mod in FORBIDDEN_MODULES or base_mod not in ALLOWED_IMPORT_MODULES:
                self.violations.append(f"Forbidden import: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            base_mod = node.module.split(".")[0]
            if base_mod in FORBIDDEN_MODULES or base_mod not in ALLOWED_IMPORT_MODULES:
                self.violations.append(f"Forbidden import from: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                self.violations.append(f"Forbidden call: '{node.func.id}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in FORBIDDEN_ATTRIBUTES:
            self.violations.append(f"Forbidden dunder attribute access: '{node.attr}'")
        self.generic_visit(node)


class ValidationReport:
    """Encapsulates validation outcome on held-out cases."""

    def __init__(
        self,
        is_safe: bool,
        status: str,
        passed_cases: int,
        total_cases: int,
        accuracy: float,
        execution_time_ms: float,
        ast_violations: List[str],
        test_results: List[Dict[str, Any]],
        error_message: Optional[str] = None
    ):
        self.is_safe = is_safe
        self.status = status  # 'validated' | 'rejected'
        self.passed_cases = passed_cases
        self.total_cases = total_cases
        self.accuracy = accuracy
        self.execution_time_ms = execution_time_ms
        self.ast_violations = ast_violations
        self.test_results = test_results
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "status": self.status,
            "passed_cases": self.passed_cases,
            "total_cases": self.total_cases,
            "accuracy": round(self.accuracy, 4),
            "execution_time_ms": round(self.execution_time_ms, 2),
            "ast_violations": self.ast_violations,
            "test_results": self.test_results,
            "error_message": self.error_message
        }


class ExecutionSandbox:
    """Safe execution environment for synthesized skills and benchmark tasks."""

    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    def check_safety(self, code_str: str) -> Tuple[bool, List[str]]:
        """Parses AST and returns (is_safe, list_of_violations)."""
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, [f"Syntax Error: {e.msg} at line {e.lineno}"]

        guard = ASTSecurityGuard()
        guard.visit(tree)
        is_safe = len(guard.violations) == 0
        return is_safe, guard.violations

    def _build_safe_environment(self) -> Dict[str, Any]:
        """Constructs safe globals dictionary."""
        env = {
            "__builtins__": SAFE_BUILTINS,
            "pd": pd,
            "np": np,
            "math": math,
            "re": re,
            "datetime": datetime,
            "json": json,
            "time": time
        }
        return env

    def execute_code(
        self,
        code_str: str,
        entrypoint: str,
        args: List[Any],
        kwargs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executes a function inside the sandbox with timeout and safety checks."""
        kwargs = kwargs or {}
        is_safe, violations = self.check_safety(code_str)
        if not is_safe:
            return {
                "success": False,
                "result": None,
                "error": f"Security Violation: {'; '.join(violations)}",
                "execution_time_ms": 0.0
            }

        start_time = time.perf_counter()

        def _worker():
            env = self._build_safe_environment()
            old_stdout = sys.stdout
            captured_out = io.StringIO()
            try:
                sys.stdout = captured_out
                exec(code_str, env)

                # Locate callable function or script result
                user_funcs = {
                    k: v for k, v in env.items()
                    if callable(v) and k not in SAFE_BUILTINS and not k.startswith('_')
                }

                target_fn = None
                if entrypoint and entrypoint in env and callable(env[entrypoint]):
                    target_fn = env[entrypoint]
                elif entrypoint and entrypoint in user_funcs:
                    target_fn = user_funcs[entrypoint]
                elif len(user_funcs) == 1:
                    target_fn = list(user_funcs.values())[0]

                if target_fn is not None and args:
                    safe_args = []
                    for a in args:
                        if isinstance(a, pd.DataFrame):
                            safe_args.append(a.copy(deep=True))
                        elif isinstance(a, (list, dict)):
                            safe_args.append(copy.deepcopy(a))
                        else:
                            safe_args.append(a)
                    fn_res = target_fn(*safe_args, **kwargs)
                    return fn_res, captured_out.getvalue()
                elif target_fn is not None and not args:
                    # Check if target_fn takes 0 args or can be called
                    try:
                        import inspect
                        sig = inspect.signature(target_fn)
                        if len(sig.parameters) == 0:
                            fn_res = target_fn()
                            return fn_res, captured_out.getvalue()
                    except Exception:
                        pass
                    return None, captured_out.getvalue()
                else:
                    # Standalone script execution (no function called or executed at top-level)
                    stdout_str = captured_out.getvalue().strip()
                    return (stdout_str if stdout_str else None), captured_out.getvalue()
            finally:
                sys.stdout = old_stdout

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(_worker)
            result, stdout = future.result(timeout=self.timeout_seconds)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "success": True,
                "result": result,
                "stdout": stdout,
                "error": None,
                "execution_time_ms": elapsed_ms
            }
        except TimeoutError:
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "error": f"Execution Timed Out (exceeded {self.timeout_seconds}s limit)",
                "execution_time_ms": (time.perf_counter() - start_time) * 1000.0
            }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "error": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
                "execution_time_ms": elapsed_ms
            }
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def validate_skill(
        self,
        code_str: str,
        entrypoint: str,
        held_out_test_cases: List[Dict[str, Any]],
        pass_threshold: float = 0.90
    ) -> ValidationReport:
        """Validates synthesized code against a suite of held-out test cases."""
        start_time = time.perf_counter()
        is_safe, violations = self.check_safety(code_str)
        if not is_safe:
            return ValidationReport(
                is_safe=False,
                status="rejected",
                passed_cases=0,
                total_cases=len(held_out_test_cases),
                accuracy=0.0,
                execution_time_ms=0.0,
                ast_violations=violations,
                test_results=[],
                error_message=f"AST Security Rejection: {'; '.join(violations)}"
            )

        passed = 0
        total = len(held_out_test_cases)
        results = []

        if total == 0:
            # Standalone / Smoke validation without explicit test assertions
            smoke_res = self.execute_code(code_str, entrypoint, [])
            smoke_pass = smoke_res["success"]
            results.append({
                "case_id": 1,
                "description": "Sandbox Execution Smoke Test",
                "passed": smoke_pass,
                "error": smoke_res.get("error"),
                "latency_ms": round(smoke_res["execution_time_ms"], 2)
            })
            passed = 1 if smoke_pass else 0
            total = 1
        else:
            for idx, test_case in enumerate(held_out_test_cases):
                inputs = test_case.get("inputs", [])
                expected = test_case.get("expected", None)
                assertion_fn = test_case.get("assertion_fn", None)
                case_desc = test_case.get("description", f"Test case #{idx+1}")

                exec_res = self.execute_code(code_str, entrypoint, inputs)
                case_pass = False
                case_err = exec_res.get("error")

                if exec_res["success"]:
                    actual = exec_res["result"]
                    try:
                        if assertion_fn and callable(assertion_fn):
                            case_pass = bool(assertion_fn(actual))
                        elif isinstance(expected, pd.DataFrame):
                            case_pass = actual.equals(expected) or actual.shape == expected.shape
                        elif isinstance(expected, float):
                            case_pass = math.isclose(actual, expected, rel_tol=1e-3, abs_tol=1e-3)
                        elif isinstance(actual, np.ndarray) and isinstance(expected, (list, np.ndarray)):
                            case_pass = np.allclose(actual, expected)
                        else:
                            case_pass = (actual == expected)
                    except Exception as comp_err:
                        case_pass = False
                        case_err = f"Assertion check error: {str(comp_err)}"
                
                if case_pass:
                    passed += 1

                results.append({
                    "case_id": idx + 1,
                    "description": case_desc,
                    "passed": case_pass,
                    "error": case_err,
                    "latency_ms": round(exec_res["execution_time_ms"], 2)
                })

        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        accuracy = (passed / total) if total > 0 else 0.0
        status = "validated" if (accuracy >= pass_threshold and is_safe) else "rejected"

        err_summary = None
        if status == "rejected":
            failed_cases = [r["description"] for r in results if not r["passed"]]
            err_summary = f"Accuracy {accuracy*100:.1f}% below {pass_threshold*100:.1f}% threshold. Failed cases: {', '.join(failed_cases[:3])}"

        return ValidationReport(
            is_safe=is_safe,
            status=status,
            passed_cases=passed,
            total_cases=total,
            accuracy=accuracy,
            execution_time_ms=total_time_ms,
            ast_violations=[],
            test_results=results,
            error_message=err_summary
        )

_sandbox = None

def get_sandbox() -> ExecutionSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = ExecutionSandbox()
    return _sandbox