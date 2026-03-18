"""Tests for script_tools.py — create_script, create_batch_script,
execute_batch_script, save_results_csv."""

import csv
import os
import sys
import tempfile

import pytest

import defense_llm.agent.script_tools as st


# ---------------------------------------------------------------------------
# Fixture: temp directory registered as an allowed path
# ---------------------------------------------------------------------------

@pytest.fixture()
def allowed_tmpdir(tmp_path):
    """Register tmp_path as allowed and clean up after test."""
    st.add_allowed_path(str(tmp_path))
    yield tmp_path
    # Cleanup: remove from list after test
    abs_path = os.path.abspath(str(tmp_path))
    if abs_path in st.ALLOWED_BASE_PATHS:
        st.ALLOWED_BASE_PATHS.remove(abs_path)


# ---------------------------------------------------------------------------
# create_script
# ---------------------------------------------------------------------------

def test_create_script_success(allowed_tmpdir):
    path = str(allowed_tmpdir / "hello.py")
    result = st.create_script(path, "print('hello')")
    assert result["success"] is True
    assert os.path.exists(path)
    assert result["size_bytes"] > 0
    assert result["error"] is None


def test_create_script_outside_allowed_raises(tmp_path):
    """Path not in allowed list must return E_AUTH error."""
    path = str(tmp_path / "bad.py")
    result = st.create_script(path, "print('x')")
    assert result["success"] is False
    assert "E_AUTH" in result["error"]


def test_create_script_no_overwrite_error(allowed_tmpdir):
    path = str(allowed_tmpdir / "exists.py")
    st.create_script(path, "x = 1")
    result = st.create_script(path, "x = 2", overwrite=False)
    assert result["success"] is False
    assert "already exists" in result["error"].lower() or "overwrite" in result["error"].lower()


def test_create_script_overwrite_true(allowed_tmpdir):
    path = str(allowed_tmpdir / "over.py")
    st.create_script(path, "x = 1")
    result = st.create_script(path, "x = 2", overwrite=True)
    assert result["success"] is True
    with open(path, encoding="utf-8") as f:
        assert "x = 2" in f.read()


def test_create_script_forbidden_os_system(allowed_tmpdir):
    path = str(allowed_tmpdir / "bad.py")
    content = "import os\nos.system('rm -rf /')"
    result = st.create_script(path, content)
    assert result["success"] is False
    assert result["error"] is not None


def test_create_script_forbidden_exec(allowed_tmpdir):
    path = str(allowed_tmpdir / "exec_bad.py")
    content = "exec('malicious code')"
    result = st.create_script(path, content)
    assert result["success"] is False


# ---------------------------------------------------------------------------
# create_batch_script
# ---------------------------------------------------------------------------

def test_create_batch_script_success(allowed_tmpdir):
    batch = str(allowed_tmpdir / "run.bat")
    script = str(allowed_tmpdir / "script.py")
    result = st.create_batch_script(batch, script)
    assert result["success"] is True
    assert os.path.exists(batch)
    assert result["error"] is None


def test_create_batch_script_content_windows(allowed_tmpdir, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    batch = str(allowed_tmpdir / "run_win.bat")
    script = r"C:\scripts\test.py"
    result = st.create_batch_script(batch, script, python_exe="python", extra_args=["--out", "result.csv"])
    assert result["success"] is True
    with open(batch, encoding="utf-8") as f:
        content = f.read()
    assert "@echo off" in content
    assert "test.py" in content
    assert "--out" in content


def test_create_batch_script_outside_allowed(tmp_path):
    batch = str(tmp_path / "run.bat")
    result = st.create_batch_script(batch, "script.py")
    assert result["success"] is False
    assert "E_AUTH" in result["error"]


# ---------------------------------------------------------------------------
# execute_batch_script
# ---------------------------------------------------------------------------

def test_execute_batch_script_success(allowed_tmpdir):
    """Create a trivial script and batch wrapper, then execute."""
    script_path = str(allowed_tmpdir / "trivial.py")
    batch_path = str(allowed_tmpdir / "trivial.bat")

    with open(script_path, "w") as f:
        f.write("print('OK')\n")

    st.create_batch_script(batch_path, script_path)
    result = st.execute_batch_script(batch_path, timeout_seconds=30)

    assert result["timed_out"] is False
    assert result["returncode"] == 0
    assert "OK" in result["stdout"]
    assert result["error"] is None


def test_execute_batch_script_not_found(allowed_tmpdir):
    batch = str(allowed_tmpdir / "missing.bat")
    result = st.execute_batch_script(batch)
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_execute_batch_script_outside_allowed(tmp_path):
    batch = str(tmp_path / "run.bat")
    result = st.execute_batch_script(batch)
    assert result["success"] is False
    assert "E_AUTH" in result["error"]


def test_execute_batch_script_timeout(allowed_tmpdir):
    """A script that sleeps must be killed by the timeout."""
    script_path = str(allowed_tmpdir / "sleep.py")
    batch_path = str(allowed_tmpdir / "sleep.bat")

    with open(script_path, "w") as f:
        f.write("import time; time.sleep(60)\n")

    st.create_batch_script(batch_path, script_path)
    result = st.execute_batch_script(batch_path, timeout_seconds=2)

    assert result["timed_out"] is True
    assert result["success"] is False


# ---------------------------------------------------------------------------
# save_results_csv
# ---------------------------------------------------------------------------

def test_save_results_csv_success(allowed_tmpdir):
    csv_path = str(allowed_tmpdir / "results.csv")
    data = [{"name": "KF-21", "speed": 1.8}, {"name": "FA-50", "speed": 1.5}]
    result = st.save_results_csv(data, csv_path)

    assert result["success"] is True
    assert result["rows_written"] == 2
    assert os.path.exists(csv_path)

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["name"] == "KF-21"


def test_save_results_csv_empty_data(allowed_tmpdir):
    csv_path = str(allowed_tmpdir / "empty.csv")
    result = st.save_results_csv([], csv_path)
    assert result["success"] is True
    assert result["rows_written"] == 0
    assert os.path.exists(csv_path)


def test_save_results_csv_outside_allowed(tmp_path):
    csv_path = str(tmp_path / "bad.csv")
    result = st.save_results_csv([{"a": 1}], csv_path)
    assert result["success"] is False
    assert "E_AUTH" in result["error"]
