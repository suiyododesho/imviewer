"""T07 unified UC1/UC2 maintenance CLI.

Commands:
- plan / dry-run: show and execute non-destructive plan steps only
- apply: execute write operations (requires explicit --approve)
- validate: sanity checks + resumability hints from state logs
- rollback: restore SQLite DB from backup

This command orchestrates existing maintenance scripts and writes
state/log artifacts for interruption-safe operations.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from .maint_metrics import RunMetrics
except ImportError:
    from maint_metrics import RunMetrics


ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT_DIR / "tools"
SITE_DIR = ROOT_DIR / "site"
DEFAULT_DB_PATH = TOOLS_DIR / "sqlite" / "imviewer_maintenance.sqlite3"
DEFAULT_STRUCTURE_PATH = SITE_DIR / "structure.json"
DEFAULT_METADATA_CSV = TOOLS_DIR / "metadata.csv"
DEFAULT_DIFF_TARGETS = ROOT_DIR / ".artifacts" / "M06" / "intermediate" / "t04-diff-targets.txt"
DEFAULT_STATE_FILE = ROOT_DIR / ".artifacts" / "M06" / "state" / "t07-uc-cli-state.jsonl"
DEFAULT_LOG_DIR = ROOT_DIR / ".artifacts" / "M06" / "logs"


@dataclass(frozen=True)
class StepSpec:
    name: str
    script: Path
    args: list[str]


@dataclass
class StepResult:
    name: str
    command: list[str]
    rc: int
    duration_ms: int
    log_path: str


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _append_state(state_file: Path, payload: dict) -> None:
    _ensure_parent(state_file)
    with state_file.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False))
        fh.write("\n")


def _read_state_lines(state_file: Path) -> list[dict]:
    if not state_file.is_file():
        return []
    lines: list[dict] = []
    for raw in state_file.read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text:
            continue
        try:
            lines.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return lines


def _latest_failed_run(state_file: Path) -> dict | None:
    for row in reversed(_read_state_lines(state_file)):
        if not row.get("success", False):
            return row
    return None


def _run_step(step: StepSpec, log_dir: Path, run_id: str) -> StepResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{stamp}_{run_id}_{step.name}.log"
    command = [sys.executable, str(step.script), *step.args]
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=str(ROOT_DIR), capture_output=True, text=True, check=False)
    duration_ms = int((time.perf_counter() - started) * 1000)

    text = []
    text.append(f"$ {' '.join(command)}")
    text.append("")
    if proc.stdout:
        text.append("[stdout]")
        text.append(proc.stdout.rstrip())
        text.append("")
    if proc.stderr:
        text.append("[stderr]")
        text.append(proc.stderr.rstrip())
        text.append("")
    text.append(f"exit_code={proc.returncode}")
    log_path.write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")

    return StepResult(
        name=step.name,
        command=command,
        rc=int(proc.returncode),
        duration_ms=duration_ms,
        log_path=str(log_path),
    )


def _build_steps(command: str, workflow: str, args: argparse.Namespace) -> list[StepSpec]:
    if command in {"plan", "dry-run", "validate"}:
        if workflow == "uc1":
            return [
                StepSpec(
                    name="t03-import-plan",
                    script=TOOLS_DIR / "maint_db_transfer.py",
                    args=[
                        "import-plan",
                        "--db",
                        str(args.db),
                        "--structure",
                        str(args.structure),
                    ],
                ),
                StepSpec(
                    name="t04-series-diff-plan",
                    script=TOOLS_DIR / "maint_series_diff.py",
                    args=[
                        "plan",
                        "--db",
                        str(args.db),
                    ],
                ),
                StepSpec(
                    name="t05-site-artifacts-plan",
                    script=TOOLS_DIR / "maint_build_site_artifacts.py",
                    args=[
                        "plan",
                        "--db",
                        str(args.db),
                        "--site-dir",
                        str(args.site_dir),
                        "--gallery-output",
                        str(args.gallery_output),
                    ],
                ),
            ]
        return [
            StepSpec(
                name="uc2-metadata-plan",
                script=TOOLS_DIR / "maint_metadata.py",
                args=[
                    "plan",
                    "--input",
                    str(args.input_csv),
                    "--diff-targets-file",
                    str(args.diff_targets_file),
                ],
            )
        ]

    if command == "apply":
        if workflow == "uc1":
            return [
                StepSpec(
                    name="t03-import-apply",
                    script=TOOLS_DIR / "maint_db_transfer.py",
                    args=[
                        "import-apply",
                        "--db",
                        str(args.db),
                        "--structure",
                        str(args.structure),
                    ],
                ),
                StepSpec(
                    name="t04-series-diff-apply",
                    script=TOOLS_DIR / "maint_series_diff.py",
                    args=[
                        "apply",
                        "--db",
                        str(args.db),
                        "--output-targets",
                        str(args.diff_targets_file),
                        "--write-history-targets",
                    ],
                ),
                StepSpec(
                    name="t05-site-artifacts-apply",
                    script=TOOLS_DIR / "maint_build_site_artifacts.py",
                    args=[
                        "apply",
                        "--db",
                        str(args.db),
                        "--site-dir",
                        str(args.site_dir),
                        "--gallery-output",
                        str(args.gallery_output),
                    ],
                ),
            ]
        return [
            StepSpec(
                name="uc2-metadata-apply",
                script=TOOLS_DIR / "maint_metadata.py",
                args=[
                    "apply",
                    "--input",
                    str(args.input_csv),
                    "--diff-targets-file",
                    str(args.diff_targets_file),
                ],
            )
        ]

    return []


def _run_workflow(command: str, workflow: str, args: argparse.Namespace) -> int:
    run_id = uuid.uuid4().hex[:10]
    state_path = Path(args.state_file)
    log_dir = Path(args.log_dir)

    steps = _build_steps(command, workflow, args)
    if not steps:
        print(json.dumps({"error": f"unsupported command/workflow: {command}/{workflow}"}, ensure_ascii=False))
        return 2

    metrics = RunMetrics("m06-t07-uc-cli", command, log_path=args.metrics_log or None)
    results: list[StepResult] = []
    success = True

    for step in steps:
        result = _run_step(step, log_dir=log_dir, run_id=run_id)
        results.append(result)
        metrics.add_stage(
            name=step.name,
            status="ok" if result.rc == 0 else "failed",
            duration_ms=result.duration_ms,
            scanned_count=1,
            generated_count=1 if result.rc == 0 else 0,
            transfer_files=0,
            transfer_bytes=0,
            details={
                "command": " ".join(result.command),
                "log_path": result.log_path,
                "exit_code": result.rc,
                "workflow": workflow,
            },
        )
        if result.rc != 0:
            success = False
            break

    metric_payload = metrics.finalize(success=success)

    payload = {
        "schema": "imviewer.m06.t07.uc_cli_state.v1",
        "run_id": run_id,
        "command": command,
        "workflow": workflow,
        "started_at": metric_payload.get("started_at"),
        "ended_at": metric_payload.get("ended_at"),
        "success": success,
        "steps": [
            {
                "name": row.name,
                "exit_code": row.rc,
                "duration_ms": row.duration_ms,
                "log_path": row.log_path,
                "command": row.command,
            }
            for row in results
        ],
        "metrics_log": metrics.log_path,
    }
    _append_state(state_path, payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Metrics log: {metrics.log_path}")
    if metric_payload.get("compare"):
        compare = metric_payload["compare"]
        print(
            "Compare(previous): "
            f"duration_ms={compare['delta_duration_ms']}, "
            f"generated={compare['delta_generated_count']}, "
            f"transfer_files={compare['delta_transfer_files']}, "
            f"transfer_bytes={compare['delta_transfer_bytes']}"
        )

    return 0 if success else 1


def _run_validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    required_paths = [Path(args.db), Path(args.structure), Path(args.site_dir)]
    for path in required_paths:
        if not path.exists():
            errors.append(f"missing: {path}")

    if args.workflow == "uc2" and not Path(args.input_csv).is_file():
        errors.append(f"missing metadata csv: {args.input_csv}")

    failed = _latest_failed_run(Path(args.state_file))
    resume_hint = ""
    if failed:
        workflow = failed.get("workflow", "")
        command = failed.get("command", "")
        resume_hint = f"Previous failed run found (workflow={workflow}, command={command}, run_id={failed.get('run_id', '')})"

    payload = {
        "schema": "imviewer.m06.t07.uc_cli_validate.v1",
        "workflow": args.workflow,
        "errors": errors,
        "resume_hint": resume_hint,
        "state_file": str(args.state_file),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if errors:
        return 1

    # Validate also executes non-destructive plan steps for target workflow.
    return _run_workflow("validate", args.workflow, args)


def _find_latest_backup(db_path: Path) -> Path | None:
    backup_dir = db_path.parent / "backup"
    if not backup_dir.is_dir():
        return None
    candidates = sorted(
        [item for item in backup_dir.glob(f"{db_path.stem}_*{db_path.suffix}.bak") if item.is_file()],
        key=lambda p: p.stat().st_mtime_ns,
    )
    return candidates[-1] if candidates else None


def _run_rollback(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    state_path = Path(args.state_file)

    if args.backup:
        backup_path = Path(args.backup)
    else:
        backup_path = _find_latest_backup(db_path)

    if backup_path is None or not backup_path.is_file():
        print(json.dumps({"error": "backup file not found", "db": str(db_path)}, ensure_ascii=False))
        return 1

    if not db_path.exists():
        print(json.dumps({"error": "db file not found", "db": str(db_path)}, ensure_ascii=False))
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rollback_backup = db_path.parent / "backup" / f"{db_path.stem}_{stamp}{db_path.suffix}.rollback.bak"
    rollback_backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, rollback_backup)
    shutil.copy2(backup_path, db_path)

    metrics = RunMetrics("m06-t07-uc-cli", "rollback", log_path=args.metrics_log or None)
    metrics.add_stage(
        name="rollback_db",
        status="ok",
        duration_ms=0,
        scanned_count=1,
        generated_count=1,
        transfer_files=1,
        transfer_bytes=db_path.stat().st_size,
        details={
            "db": str(db_path),
            "source_backup": str(backup_path),
            "rollback_backup": str(rollback_backup),
        },
    )
    metrics.finalize(success=True)

    payload = {
        "schema": "imviewer.m06.t07.uc_cli_state.v1",
        "run_id": uuid.uuid4().hex[:10],
        "command": "rollback",
        "workflow": "uc1",
        "started_at": _iso_now(),
        "ended_at": _iso_now(),
        "success": True,
        "steps": [
            {
                "name": "rollback_db",
                "exit_code": 0,
                "duration_ms": 0,
                "log_path": "",
                "command": ["copy", str(backup_path), str(db_path)],
            }
        ],
        "metrics_log": metrics.log_path,
    }
    _append_state(state_path, payload)

    print(
        json.dumps(
            {
                "db": str(db_path),
                "restored_from": str(backup_path),
                "rollback_backup": str(rollback_backup),
                "metrics_log": metrics.log_path,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="T07 unified UC1/UC2 maintenance CLI")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="JSONL state log path")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="Directory for per-step logs")
    parser.add_argument("--metrics-log", default="", help="Optional JSONL metrics output path")

    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "dry-run", "apply", "validate"):
        cmd = sub.add_parser(name, help=f"{name} workflow")
        cmd.add_argument("workflow", choices=("uc1", "uc2"), help="Target use-case workflow")
        cmd.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
        cmd.add_argument("--structure", default=str(DEFAULT_STRUCTURE_PATH), help="structure.json path")
        cmd.add_argument("--site-dir", default=str(SITE_DIR), help="site directory path")
        cmd.add_argument("--input-csv", default=str(DEFAULT_METADATA_CSV), help="metadata CSV path")
        cmd.add_argument("--diff-targets-file", default=str(DEFAULT_DIFF_TARGETS), help="diff targets file")
        cmd.add_argument(
            "--gallery-output",
            choices=("compat", "split", "both"),
            default="both",
            help="gallery-pages output mode for UC1",
        )
        if name == "apply":
            cmd.add_argument(
                "--approve",
                action="store_true",
                help="Required safety flag for write operations",
            )

    rollback = sub.add_parser("rollback", help="restore DB from backup")
    rollback.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
    rollback.add_argument("--backup", default="", help="Backup file path (default: latest)")

    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.command in {"plan", "dry-run"}:
        return _run_workflow(args.command, args.workflow, args)

    if args.command == "validate":
        return _run_validate(args)

    if args.command == "apply":
        if not bool(args.approve):
            print("ERROR: apply requires --approve for safety.", file=sys.stderr)
            return 2
        return _run_workflow("apply", args.workflow, args)

    if args.command == "rollback":
        return _run_rollback(args)

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
