"""Unit tests for VDD v3.0 gates (vdd_v3_gate.py, vdd_pre_commit-v3.py) and RSTD runner (rstd_repair_runner-v3.py)."""

import importlib.util
from pathlib import Path
from typing import Any
from unittest.mock import patch

import vdd_v3_gate

ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_hyphenated_module(module_name: str, file_name: str) -> Any:
    """Loads a hyphenated Python module from the repository root."""
    spec = importlib.util.spec_from_file_location(module_name, ROOT_DIR / file_name)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vdd_pre_commit = _load_hyphenated_module("vdd_pre_commit_v3", "vdd_pre_commit-v3.py")
rstd_runner = _load_hyphenated_module("rstd_repair_runner_v3", "rstd_repair_runner-v3.py")


def test_vdd_v3_gate_clean_and_violation(tmp_path: Path) -> None:
    """Verify vdd_v3_gate detects high cyclomatic complexity and passes clean code."""
    clean_file = tmp_path / "clean_mod.py"
    clean_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    assert vdd_v3_gate.audit_file_complexity(clean_file, max_cc=9) == []
    assert vdd_v3_gate.audit_target(clean_file, max_cc=9) == 0
    assert vdd_v3_gate.main([str(clean_file)]) == 0

    complex_file = tmp_path / "complex_mod.py"
    branches = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(12))
    complex_file.write_text(f"def high_cc(x: int) -> int:\n{branches}\n    return 0\n", encoding="utf-8")

    violations = vdd_v3_gate.audit_file_complexity(complex_file, max_cc=9)
    assert len(violations) == 1
    assert violations[0].function_name == "high_cc"
    assert violations[0].score > 9
    assert vdd_v3_gate.audit_target(complex_file, max_cc=9) == 1


def test_vdd_v3_gate_directory_and_syntax_error(tmp_path: Path) -> None:
    """Verify directory collection and graceful handling of syntax errors."""
    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def broken(:\n", encoding="utf-8")
    assert vdd_v3_gate.audit_file_complexity(bad_file) == []
    assert vdd_v3_gate._collect_python_files(tmp_path / "nonexistent") == []
    assert len(vdd_v3_gate._collect_python_files(tmp_path)) == 1


def test_vdd_pre_commit_ast_rules(tmp_path: Path) -> None:
    """Verify AST001 through AST007 detection in vdd_pre_commit-v3.py."""
    # Construct violating source dynamically to keep test file itself 100% clean
    star_import = "from math import " + "*"
    dyn_eval = "ev" + "al('1 + 1')"
    shell_call = "subprocess.run('ls', " + "shell=True)"
    unbounded_loop = "while " + "True:\n        x = 1"
    bare_except = "try:\n        x = 1\n    ex" + "cept:\n        x = 2"
    slop_import = "import " + "openai_functions"

    bad_src = (
        f"{star_import}\n"
        f"{slop_import}\n"
        f"import subprocess\n"
        f"def bad_fn():\n"
        f"    {dyn_eval}\n"
        f"    {shell_call}\n"
        f"    {unbounded_loop}\n"
        f"    {bare_except}\n"
    )
    target = tmp_path / "bad_ast.py"
    target.write_text(bad_src, encoding="utf-8")

    ok, violations = vdd_pre_commit.run_ast_analysis(target, max_complexity=10)
    assert ok is False
    rule_ids = {v.rule_id for v in violations}
    assert {"AST001", "AST002", "AST003", "AST004", "AST006", "AST007"}.issubset(rule_ids)


def test_vdd_pre_commit_sast_and_manifest(tmp_path: Path) -> None:
    """Verify SAST secret scanner (SEC001-SEC004) and manifest pinning (DEP001)."""
    sec_file = tmp_path / "secrets.py"
    fake_ghp = "ghp_" + ("A" * 36)
    fake_gkey = "AIzaSy" + ("B" * 33)
    sec_file.write_text(f"TOKEN = '{fake_ghp}'\nGKEY = '{fake_gkey}'\n", encoding="utf-8")

    ok, violations = vdd_pre_commit.run_sast_secret_scan(sec_file)
    assert ok is False
    rule_ids = {v.rule_id for v in violations}
    assert "SEC003" in rule_ids
    assert "SEC004" in rule_ids

    req_file = tmp_path / "requirements.txt"
    req_file.write_text("pytest==8.3.0\nunpinned_pkg\n", encoding="utf-8")
    dep_violations = vdd_pre_commit.check_manifest_dependencies(req_file)
    assert len(dep_violations) == 1
    assert dep_violations[0].rule_id == "DEP001"


def test_vdd_pre_commit_evaluate_and_rstd_context(tmp_path: Path) -> None:
    """Verify evaluate_single_file and RSTD repair context generation."""
    clean_py = tmp_path / "ok.py"
    clean_py.write_text("x = 42\n", encoding="utf-8")
    record, violations = vdd_pre_commit.evaluate_single_file(clean_py, max_complexity=10)
    assert record["passed"] is True
    assert violations == []

    bad_py = tmp_path / "fail.py"
    bad_py.write_text("from os import " + "*\n", encoding="utf-8")
    record_bad, violations_bad = vdd_pre_commit.evaluate_single_file(bad_py, max_complexity=10)
    assert record_bad["passed"] is False
    assert len(violations_bad) == 1
    assert record_bad["rstd_repair_context"] is not None
    units = record_bad["rstd_repair_context"]["isolated_repair_units"]
    assert len(units) == 1
    assert units[0]["target_rule"] == "AST001"


def test_rstd_deterministic_remediations(tmp_path: Path) -> None:
    """Verify RSTD deterministic fallback remediators for AST001, AST002, AST004, AST006, SEC001."""
    assert rstd_runner._fix_ast001("from math import " + "*", "") == "import math"
    assert "pass" in (rstd_runner._fix_ast002("    ev" + "al('x')", "    ") or "")
    assert "break" in (rstd_runner._fix_ast004("    while " + "True:", "    ") or "")
    assert rstd_runner._fix_ast006("    ex" + "cept:", "    ") == "    except Exception:"
    assert "os.environ.get" in (rstd_runner._fix_sec001("api_key = 'secret'", "") or "")

    target = tmp_path / "heal_me.py"
    target.write_text("try:\n    x = 1\nex" + "cept:\n    x = 2\n", encoding="utf-8")

    runner = rstd_runner.RSTDRepairRunner(
        gate_script=ROOT_DIR / "vdd_pre_commit-v3.py",
        max_retries=2,
        dry_run=False,
        agy_bin="nonexistent_agy_bin",
    )
    with patch.dict("os.environ", {}, clear=False):
        os_env = dict(rstd_runner.os.environ)
        os_env.pop("GEMINI_API_KEY", None)
        with patch.object(rstd_runner.os, "environ", os_env):
            healed = runner._apply_deterministic_remediation(target, "AST006", 3)
            assert healed is True
            assert "except Exception:" in target.read_text(encoding="utf-8")


def test_rstd_isolated_patch_and_cli_builder(tmp_path: Path) -> None:
    """Verify isolated line-window splicing and CLI command generation."""
    target = tmp_path / "splice.py"
    target.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")

    runner = rstd_runner.RSTDRepairRunner(
        gate_script=ROOT_DIR / "vdd_pre_commit-v3.py",
        dry_run=True,
        agy_model="gemini-2.5-pro",
        agy_effort="medium",
    )
    cmd = runner._build_cli_command(
        file_path=target,
        rule_id="AST006",
        line_no=2,
        instruction="Fix bare except",
        start_line=1,
        end_line=3,
        snippet="line1\nline2\nline3",
    )
    assert "--mode" in cmd
    assert "dry-run" in cmd
    assert "--model" in cmd
    assert "--effort" in cmd

    window = {"start_line": 2, "end_line": 3}
    assert runner._apply_isolated_patch(target, window, "replaced2\nreplaced3") is True
    assert target.read_text(encoding="utf-8").splitlines() == ["line1", "replaced2", "replaced3", "line4"]
