import ast
import base64
import json
import subprocess
import sys
from typing import Any


CODE_TIMEOUT_SECONDS = 15
MAX_CODE_LENGTH = 20_000

# Denylist, not allowlist: matplotlib code is too varied in shape (loops for annotating bars,
# f-string titles, comprehensions building series) to safely enumerate every legitimate node type
# without breaking real usage. The actual hard boundary is the restricted exec() environment and
# the empty-environment subprocess in _run_sandboxed() below — this AST pass is a cheap first
# filter that catches the obvious cases (import, exec/eval, dunder access) before we ever spawn it.
_FORBIDDEN_NODE_TYPES = (
    ast.Import,
    ast.ImportFrom,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Global,
    ast.Nonlocal,
    ast.Delete,
)
_FORBIDDEN_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "input",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "__builtins__", "__loader__", "__spec__", "breakpoint", "memoryview",
}


def validate_chart_code(code: str) -> None:
    """Reject anything that isn't plain data-shaping + matplotlib calls."""
    if len(code) > MAX_CODE_LENGTH:
        raise ValueError("Chart code is too long")
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Chart code has a syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODE_TYPES):
            raise ValueError(f"Chart code may not use {type(node).__name__} — only plain plotting calls")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"Chart code may not reference '{node.id}'")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Chart code may not access dunder attributes")


# Runs in a *separate OS process launched with an empty environment* (see _run_sandboxed): even a
# full sandbox escape here inherits no Azure SQL/Foundry credentials to steal, and the process is
# killed on a timeout regardless. df/code arrive over stdin as JSON, never as a file or import.
_RUNNER_SCRIPT = r"""
import sys, json, base64, io

def main():
    payload = json.loads(sys.stdin.read())
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.DataFrame(payload["rows"])
    code = payload["code"]

    safe_builtins = {
        "range": range, "len": len, "min": min, "max": max, "sum": sum, "sorted": sorted,
        "enumerate": enumerate, "zip": zip, "round": round, "abs": abs, "map": map, "filter": filter,
        "list": list, "dict": dict, "tuple": tuple, "set": set, "str": str, "int": int,
        "float": float, "bool": bool, "print": print, "isinstance": isinstance,
        "True": True, "False": False, "None": None,
    }
    exec_globals = {"__builtins__": safe_builtins, "pd": pd, "plt": plt, "df": df}
    exec(compile(code, "<chart_code>", "exec"), exec_globals)

    fig = exec_globals.get("fig")
    if fig is None:
        print(json.dumps({"error": "Chart code must assign a matplotlib Figure to a variable named fig"}))
        return

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    print(json.dumps({"image_base64": base64.b64encode(buf.getvalue()).decode("ascii")}))

try:
    main()
except Exception as exc:
    print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
"""


def render_chart_image(rows: list[dict[str, Any]], code: str, timeout: float = CODE_TIMEOUT_SECONDS) -> bytes:
    """Validate, then execute chart code against real rows in an isolated subprocess. Returns PNG bytes."""
    validate_chart_code(code)
    payload = json.dumps({"rows": rows, "code": code})
    try:
        result = subprocess.run(
            [sys.executable, "-c", _RUNNER_SCRIPT],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={},  # no inherited env vars — nothing to steal even on a full sandbox escape
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Chart code timed out after {timeout}s") from exc

    if result.returncode != 0:
        raise ValueError(f"Chart code process failed: {result.stderr.strip()[:500]}")
    try:
        output = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise ValueError("Chart code produced no usable output") from exc

    if "error" in output:
        raise ValueError(output["error"])
    return base64.b64decode(output["image_base64"])
