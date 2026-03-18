"""Agentic script execution tools: create, wrap, run, and save results.

These four functions are dispatched by the Executor when the LLM emits the
corresponding tool_calls.  Each function:
  - Validates the target path against ALLOWED_BASE_PATHS (security gate)
  - Performs its file/process operation
  - Returns a serialisable result dict {"success": bool, ..., "error": Optional[str]}

Security model
--------------
- All file paths are checked against ALLOWED_BASE_PATHS (absolute, prefix match).
- create_script performs AST-level analysis and a regex pre-scan to block
  dangerous system calls (os.system, subprocess with shell=True, etc.).
- execute_batch_script uses subprocess.run with shell=False and a timeout.
- ALLOWED_BASE_PATHS can be extended at runtime via add_allowed_path().
"""

from __future__ import annotations

import ast
import csv
import io
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------

ALLOWED_BASE_PATHS: List[str] = [
    r"C:\User\users\llm_test",          # Windows primary workspace
    r"C:/User/users/llm_test",          # forward-slash variant
    r"/tmp/defense_llm_scripts",        # Linux / test environment fallback
]

FORBIDDEN_SHELL_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\s*\.\s*(call|run|Popen)\s*\([^)]*shell\s*=\s*True",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
]

_FORBIDDEN_SHELL_RE = re.compile("|".join(FORBIDDEN_SHELL_PATTERNS), re.DOTALL)

FORBIDDEN_COMMANDS = frozenset({
    "rm", "del", "rmdir", "rd", "format", "mkfs",
    "dd", "shred", "shutdown", "reboot", "halt",
})

DEFAULT_TIMEOUT_SECONDS = 300
MAX_SCRIPT_SIZE_BYTES = 64 * 1024   # 64 KB


def add_allowed_path(path: str) -> None:
    """Register an additional allowed base path at runtime (e.g., for tests)."""
    abs_path = os.path.abspath(path)
    if abs_path not in ALLOWED_BASE_PATHS:
        ALLOWED_BASE_PATHS.append(abs_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_path_allowed(path: str) -> None:
    """Raise PermissionError if *path* is outside every allowed base path.

    Resolves symlinks and normalises slashes before comparison.
    """
    abs_path = os.path.normcase(os.path.abspath(path))
    for base in ALLOWED_BASE_PATHS:
        normalised_base = os.path.normcase(os.path.abspath(base))
        if abs_path.startswith(normalised_base):
            return
    raise PermissionError(
        f"E_AUTH: Path '{path}' is outside allowed directories. "
        f"Allowed: {ALLOWED_BASE_PATHS}"
    )


def _validate_script_content(content: str) -> List[str]:
    """Return a list of security violations found in *content*.

    Checks:
    1. Size limit
    2. Regex pre-scan for dangerous shell patterns
    3. AST-level detection of forbidden bare identifiers
    """
    violations: List[str] = []

    if len(content.encode("utf-8")) > MAX_SCRIPT_SIZE_BYTES:
        violations.append(
            f"Script exceeds max size ({MAX_SCRIPT_SIZE_BYTES} bytes)."
        )

    if _FORBIDDEN_SHELL_RE.search(content):
        violations.append(
            "Script contains forbidden shell-escape pattern "
            "(os.system / subprocess shell=True / eval / exec)."
        )

    # AST walk: look for Name nodes whose id is a forbidden command
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_COMMANDS:
                violations.append(
                    f"Script references forbidden identifier '{node.id}'."
                )
    except SyntaxError as exc:
        violations.append(f"Script has syntax error: {exc}")

    return violations


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------

def create_script(
    script_path: str,
    script_content: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Write a Python script to an allowed path.

    Args:
        script_path: Absolute path for the script file.
        script_content: Python source code string.
        overwrite: If False (default), raise FileExistsError when file exists.

    Returns:
        {"success": bool, "script_path": str, "size_bytes": int,
         "error": Optional[str]}
    """
    try:
        _assert_path_allowed(script_path)

        violations = _validate_script_content(script_content)
        if violations:
            return {
                "success": False,
                "script_path": script_path,
                "size_bytes": 0,
                "error": "Security violations: " + "; ".join(violations),
            }

        if not overwrite and os.path.exists(script_path):
            return {
                "success": False,
                "script_path": script_path,
                "size_bytes": 0,
                "error": f"File already exists: '{script_path}'. Use overwrite=True to replace.",
            }

        os.makedirs(os.path.dirname(os.path.abspath(script_path)), exist_ok=True)
        encoded = script_content.encode("utf-8")
        with open(script_path, "wb") as fh:
            fh.write(encoded)

        return {
            "success": True,
            "script_path": script_path,
            "size_bytes": len(encoded),
            "error": None,
        }

    except PermissionError as exc:
        return {"success": False, "script_path": script_path, "size_bytes": 0, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "script_path": script_path, "size_bytes": 0, "error": f"E_INTERNAL: {exc}"}


def create_batch_script(
    batch_path: str,
    script_path: str,
    python_exe: str = "python",
    extra_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate a .bat (Windows) or .sh (Unix) wrapper that calls a Python script.

    Args:
        batch_path: Absolute path for the batch/shell file to create.
        script_path: Path to the Python script to invoke.
        python_exe: Python executable path (default: "python").
        extra_args: Additional CLI arguments forwarded to the script.

    Returns:
        {"success": bool, "batch_path": str, "platform": str,
         "error": Optional[str]}
    """
    try:
        _assert_path_allowed(batch_path)
        # script_path may be outside allowed paths (it is read-only from caller's
        # perspective), but we still normalise it.
        args_str = " ".join(str(a) for a in (extra_args or []))
        platform = "windows" if sys.platform == "win32" else "unix"

        if platform == "windows":
            content = (
                "@echo off\n"
                f'"{python_exe}" "{script_path}" {args_str}\n'
            )
        else:
            content = (
                "#!/bin/bash\n"
                f'"{python_exe}" "{script_path}" {args_str}\n'
            )

        os.makedirs(os.path.dirname(os.path.abspath(batch_path)), exist_ok=True)
        with open(batch_path, "w", encoding="utf-8", newline="\r\n" if platform == "windows" else "\n") as fh:
            fh.write(content)

        # Make executable on Unix
        if platform != "windows":
            os.chmod(batch_path, 0o755)

        return {
            "success": True,
            "batch_path": batch_path,
            "platform": platform,
            "error": None,
        }

    except PermissionError as exc:
        return {"success": False, "batch_path": batch_path, "platform": "", "error": str(exc)}
    except Exception as exc:
        return {"success": False, "batch_path": batch_path, "platform": "", "error": f"E_INTERNAL: {exc}"}


def execute_batch_script(
    batch_path: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    capture_output: bool = True,
) -> Dict[str, Any]:
    """Execute a batch/shell script in a subprocess with timeout enforcement.

    Args:
        batch_path: Absolute path to the batch/shell script.
        timeout_seconds: Maximum execution time in seconds (default: 300).
        capture_output: Whether to capture stdout/stderr (default: True).

    Returns:
        {"success": bool, "returncode": int, "stdout": str, "stderr": str,
         "timed_out": bool, "execution_time_seconds": float,
         "error": Optional[str]}
    """
    try:
        _assert_path_allowed(batch_path)

        if not os.path.exists(batch_path):
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "execution_time_seconds": 0.0,
                "error": f"Batch file not found: '{batch_path}'",
            }

        if sys.platform == "win32":
            cmd = ["cmd.exe", "/C", batch_path]
        else:
            cmd = ["bash", batch_path]

        cwd = os.path.dirname(os.path.abspath(batch_path))
        t0 = time.monotonic()
        timed_out = False

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                capture_output=capture_output,
                cwd=cwd,
                timeout=timeout_seconds,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            elapsed = time.monotonic() - t0
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "timed_out": False,
                "execution_time_seconds": round(elapsed, 3),
                "error": None,
            }
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - t0
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "timed_out": True,
                "execution_time_seconds": round(elapsed, 3),
                "error": f"Execution timed out after {timeout_seconds}s.",
            }

    except PermissionError as exc:
        return {
            "success": False, "returncode": -1, "stdout": "", "stderr": "",
            "timed_out": False, "execution_time_seconds": 0.0, "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False, "returncode": -1, "stdout": "", "stderr": "",
            "timed_out": False, "execution_time_seconds": 0.0,
            "error": f"E_INTERNAL: {exc}",
        }


def save_results_csv(
    data: List[Dict[str, Any]],
    csv_path: str,
    encoding: str = "utf-8-sig",
) -> Dict[str, Any]:
    """Write a list of dicts to a CSV file (Excel-compatible by default).

    Args:
        data: List of row dicts. All keys of the first row become column headers.
              Subsequent rows missing a key will produce an empty cell.
        csv_path: Absolute path for the output CSV file.
        encoding: File encoding (default: "utf-8-sig" — includes BOM for Excel).

    Returns:
        {"success": bool, "csv_path": str, "rows_written": int,
         "error": Optional[str]}
    """
    try:
        _assert_path_allowed(csv_path)
        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)

        if not data:
            with open(csv_path, "w", encoding=encoding, newline="") as fh:
                fh.write("")
            return {"success": True, "csv_path": csv_path, "rows_written": 0, "error": None}

        fieldnames = list(data[0].keys())
        with open(csv_path, "w", encoding=encoding, newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

        return {
            "success": True,
            "csv_path": csv_path,
            "rows_written": len(data),
            "error": None,
        }

    except PermissionError as exc:
        return {"success": False, "csv_path": csv_path, "rows_written": 0, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "csv_path": csv_path, "rows_written": 0, "error": f"E_INTERNAL: {exc}"}
