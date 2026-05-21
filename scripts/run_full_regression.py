#!/usr/bin/env python3
"""
CATBot master regression runner.

Codex entry point for a full regression run:
    python scripts/run_full_regression.py

The runner intentionally executes only predefined local suites. It does not
accept arbitrary shell commands.
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.runtime_env import build_script_env, resolve_project_root, resolve_venv_python


DEFAULT_SUITE_ORDER = (
    "python-tests",
    "electron-verify",
    "javascript-syntax",
)

JAVASCRIPT_SOURCE_DIRS = (
    "js",
    "electron-app/main",
    "electron-app/renderer/avatar",
    "electron-app/renderer/control-panel",
)

JAVASCRIPT_SOURCE_FILES = (
    "ai-autogen-call.js",
    "recorder-worklet-processor.js",
    "test_endpoint.js",
)

JAVASCRIPT_EXCLUDED_PARTS = {
    "node_modules",
    "vendor",
    "dist",
    "dist-win",
}


@dataclass(frozen=True)
class RegressionContext:
    project_root: Path
    python_exe: str
    env: dict[str, str]
    timeout_multiplier: float = 1.0


@dataclass(frozen=True)
class SuiteResult:
    name: str
    status: str
    elapsed_seconds: float
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"PASS", "SKIP"}


@dataclass(frozen=True)
class RegressionSuite:
    name: str
    description: str
    runner: Callable[[RegressionContext], SuiteResult]


def _display_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _scaled_timeout(base_seconds: int, multiplier: float) -> int:
    return max(1, int(round(base_seconds * max(0.1, multiplier))))


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> int:
    print(f"$ {_display_command(command)}", flush=True)
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            timeout=timeout_seconds,
        )
        return int(completed.returncode)
    except FileNotFoundError:
        print(f"Command not found: {command[0]}", flush=True)
        return 127
    except subprocess.TimeoutExpired:
        print(f"Timed out after {timeout_seconds} seconds: {_display_command(command)}", flush=True)
        return 124


def _run_single_command_suite(
    name: str,
    command: list[str],
    context: RegressionContext,
    *,
    timeout_seconds: int,
) -> SuiteResult:
    started_at = time.monotonic()
    exit_code = _run_command(
        command,
        cwd=context.project_root,
        env=context.env,
        timeout_seconds=_scaled_timeout(timeout_seconds, context.timeout_multiplier),
    )
    elapsed = time.monotonic() - started_at
    if exit_code == 0:
        return SuiteResult(name=name, status="PASS", elapsed_seconds=elapsed)
    return SuiteResult(
        name=name,
        status="FAIL",
        elapsed_seconds=elapsed,
        message=f"exit code {exit_code}",
    )


def run_python_tests(context: RegressionContext) -> SuiteResult:
    cache_dir = context.project_root / "scratch" / "regression" / "pytest_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    test_files = discover_pytest_files(context.project_root)
    if not test_files:
        return SuiteResult(
            name="python-tests",
            status="SKIP",
            elapsed_seconds=0.0,
            message="no pytest files found",
        )

    started_at = time.monotonic()
    failures: list[str] = []
    for test_file in test_files:
        relative_path = str(test_file.relative_to(context.project_root))
        exit_code = _run_command(
            [
                context.python_exe,
                "-m",
                "pytest",
                relative_path,
                "-v",
                "-o",
                f"cache_dir={cache_dir}",
            ],
            cwd=context.project_root,
            env=context.env,
            timeout_seconds=_scaled_timeout(600, context.timeout_multiplier),
        )
        if exit_code != 0:
            failures.append(f"{relative_path} exited {exit_code}")

    elapsed = time.monotonic() - started_at
    if failures:
        return SuiteResult(
            name="python-tests",
            status="FAIL",
            elapsed_seconds=elapsed,
            message="; ".join(failures),
        )
    return SuiteResult(
        name="python-tests",
        status="PASS",
        elapsed_seconds=elapsed,
        message=f"{len(test_files)} files run",
    )


def discover_pytest_files(project_root: Path) -> list[Path]:
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return []
    return sorted(
        path
        for path in tests_dir.rglob("test_*.py")
        if path.is_file() and "__pycache__" not in path.parts
    )


def run_electron_verify(context: RegressionContext) -> SuiteResult:
    return _run_single_command_suite(
        "electron-verify",
        [
            context.python_exe,
            "electron-app/scripts/verify_electron_install.py",
        ],
        context,
        timeout_seconds=120,
    )


def discover_javascript_syntax_files(project_root: Path) -> list[Path]:
    files: list[Path] = []

    for relative_file in JAVASCRIPT_SOURCE_FILES:
        path = project_root / relative_file
        if path.is_file():
            files.append(path)

    for relative_dir in JAVASCRIPT_SOURCE_DIRS:
        directory = project_root / relative_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.js")):
            relative_parts = set(path.relative_to(project_root).parts)
            if relative_parts & JAVASCRIPT_EXCLUDED_PARTS:
                continue
            files.append(path)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


def run_javascript_syntax(context: RegressionContext) -> SuiteResult:
    node_exe = shutil.which("node", path=context.env.get("PATH")) or shutil.which("node")
    if not node_exe:
        return SuiteResult(
            name="javascript-syntax",
            status="FAIL",
            elapsed_seconds=0.0,
            message="node executable not found",
        )

    files = discover_javascript_syntax_files(context.project_root)
    if not files:
        return SuiteResult(
            name="javascript-syntax",
            status="SKIP",
            elapsed_seconds=0.0,
            message="no JavaScript source files found",
        )

    started_at = time.monotonic()
    failures: list[str] = []
    for path in files:
        relative_path = str(path.relative_to(context.project_root))
        exit_code = _run_command(
            [node_exe, "--check", relative_path],
            cwd=context.project_root,
            env=context.env,
            timeout_seconds=_scaled_timeout(60, context.timeout_multiplier),
        )
        if exit_code != 0:
            failures.append(f"{relative_path} exited {exit_code}")

    elapsed = time.monotonic() - started_at
    if failures:
        return SuiteResult(
            name="javascript-syntax",
            status="FAIL",
            elapsed_seconds=elapsed,
            message="; ".join(failures),
        )
    return SuiteResult(
        name="javascript-syntax",
        status="PASS",
        elapsed_seconds=elapsed,
        message=f"{len(files)} files checked",
    )


def build_suite_registry() -> dict[str, RegressionSuite]:
    return {
        "python-tests": RegressionSuite(
            name="python-tests",
            description="Run every tests/test_*.py file with pytest.",
            runner=run_python_tests,
        ),
        "electron-verify": RegressionSuite(
            name="electron-verify",
            description="Run the Electron desktop workspace verifier.",
            runner=run_electron_verify,
        ),
        "javascript-syntax": RegressionSuite(
            name="javascript-syntax",
            description="Run node --check against CATBot-owned JavaScript sources.",
            runner=run_javascript_syntax,
        ),
    }


def _expand_suite_names(raw_suite_args: list[str] | None) -> list[str]:
    if not raw_suite_args:
        return list(DEFAULT_SUITE_ORDER)

    suite_names: list[str] = []
    for raw in raw_suite_args:
        for item in raw.split(","):
            name = item.strip()
            if name:
                suite_names.append(name)
    return suite_names


def build_context(timeout_multiplier: float = 1.0) -> RegressionContext:
    project_root = resolve_project_root()
    python_exe = resolve_venv_python(project_root)
    env = build_script_env(project_root, python_exe=python_exe)
    temp_dir = project_root / "scratch" / "regression" / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["TMPDIR"] = str(temp_dir)
    return RegressionContext(
        project_root=project_root,
        python_exe=python_exe,
        env=env,
        timeout_multiplier=timeout_multiplier,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CATBot's master regression suite.",
    )
    parser.add_argument(
        "--suite",
        action="append",
        help="Suite to run. Repeat or comma-separate values. Defaults to all suites.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available regression suites and exit.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing suite.",
    )
    parser.add_argument(
        "--timeout-multiplier",
        type=float,
        default=1.0,
        help="Scale per-suite timeouts. Default: 1.0.",
    )
    return parser.parse_args(argv)


def print_suite_list(registry: dict[str, RegressionSuite]) -> None:
    print("Available regression suites:")
    for name in DEFAULT_SUITE_ORDER:
        suite = registry[name]
        print(f"  {suite.name}: {suite.description}")


def print_summary(results: list[SuiteResult]) -> None:
    print("\nRegression summary:")
    for result in results:
        detail = f" - {result.message}" if result.message else ""
        print(f"  {result.status:4} {result.name} ({result.elapsed_seconds:.1f}s){detail}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry = build_suite_registry()

    if args.list:
        print_suite_list(registry)
        return 0

    suite_names = _expand_suite_names(args.suite)
    unknown = [name for name in suite_names if name not in registry]
    if unknown:
        print(f"Unknown regression suite(s): {', '.join(unknown)}", file=sys.stderr)
        print_suite_list(registry)
        return 2

    context = build_context(timeout_multiplier=args.timeout_multiplier)
    print("CATBot full regression")
    print(f"Project root: {context.project_root}")
    print(f"Python: {context.python_exe}")
    print(f"Suites: {', '.join(suite_names)}\n")

    results: list[SuiteResult] = []
    for index, suite_name in enumerate(suite_names, start=1):
        suite = registry[suite_name]
        print(f"[{index}/{len(suite_names)}] {suite.name}: {suite.description}", flush=True)
        result = suite.runner(context)
        results.append(result)
        detail = f" - {result.message}" if result.message else ""
        print(f"{result.status} {result.name} in {result.elapsed_seconds:.1f}s{detail}\n", flush=True)
        if args.fail_fast and not result.ok:
            break

    print_summary(results)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
