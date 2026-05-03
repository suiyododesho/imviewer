"""Shared measurement helpers for M06 maintenance instrumentation."""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
import uuid


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def default_metrics_log_path(pipeline: str) -> str:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    safe = pipeline.replace(" ", "-").replace("/", "-")
    return os.path.join(root_dir, ".artifacts", "M06", "metrics", f"{safe}.jsonl")


def _iter_files(path: str):
    if not path:
        return
    if os.path.isfile(path):
        yield os.path.abspath(path)
        return
    if not os.path.isdir(path):
        return
    for dir_path, _, files in os.walk(path):
        for name in files:
            yield os.path.join(dir_path, name)


def snapshot_files(paths: list[str]) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for root in paths:
        for file_path in _iter_files(root):
            try:
                stat = os.stat(file_path)
            except OSError:
                continue
            snapshot[file_path] = (int(stat.st_size), int(stat.st_mtime_ns))
    return snapshot


def summarize_snapshot(snapshot: dict[str, tuple[int, int]]) -> tuple[int, int]:
    file_count = len(snapshot)
    total_bytes = sum(size for size, _mtime in snapshot.values())
    return file_count, int(total_bytes)


def summarize_diff(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> dict[str, int]:
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    created = after_keys - before_keys
    deleted = before_keys - after_keys
    common = before_keys & after_keys
    modified = {k for k in common if before[k] != after[k]}

    generated_count = len(created) + len(modified)
    transfer_files = len(created) + len(modified) + len(deleted)
    transfer_bytes = 0
    for key in created | modified:
        transfer_bytes += after[key][0]
    for key in deleted:
        transfer_bytes += before[key][0]

    return {
        "generated_count": int(generated_count),
        "transfer_files": int(transfer_files),
        "transfer_bytes": int(transfer_bytes),
        "created_files": int(len(created)),
        "modified_files": int(len(modified)),
        "deleted_files": int(len(deleted)),
    }


class RunMetrics:
    """Collects per-stage timings and writes JSONL metrics logs."""

    def __init__(self, pipeline: str, mode: str, log_path: str | None = None):
        self.pipeline = pipeline
        self.mode = mode
        self.run_id = uuid.uuid4().hex
        self.started_at = _iso_now()
        self._started_ts = time.perf_counter()
        self.log_path = log_path or default_metrics_log_path(pipeline)
        self.stages: list[dict] = []

    def plan_stage(self, name: str, details: dict | None = None) -> None:
        self.stages.append(
            {
                "name": name,
                "status": "planned",
                "duration_ms": 0,
                "scanned_count": 0,
                "generated_count": 0,
                "transfer_files": 0,
                "transfer_bytes": 0,
                "details": details or {},
            }
        )

    def begin_stage(self, name: str, monitor_paths: list[str], details: dict | None = None) -> dict:
        before = snapshot_files(monitor_paths)
        scanned_count, scanned_bytes = summarize_snapshot(before)
        return {
            "name": name,
            "details": details or {},
            "before": before,
            "scanned_count": scanned_count,
            "scanned_bytes": scanned_bytes,
            "started_ts": time.perf_counter(),
            "monitor_paths": monitor_paths,
        }

    def end_stage(self, token: dict, status: str = "ok", details: dict | None = None) -> dict:
        after = snapshot_files(token["monitor_paths"])
        diff = summarize_diff(token["before"], after)
        duration_ms = int((time.perf_counter() - token["started_ts"]) * 1000)
        merged_details = dict(token.get("details") or {})
        if details:
            merged_details.update(details)
        stage = {
            "name": token["name"],
            "status": status,
            "duration_ms": duration_ms,
            "scanned_count": int(token["scanned_count"]),
            "generated_count": int(diff["generated_count"]),
            "transfer_files": int(diff["transfer_files"]),
            "transfer_bytes": int(diff["transfer_bytes"]),
            "details": {
                "scanned_bytes": int(token["scanned_bytes"]),
                **merged_details,
                "created_files": int(diff["created_files"]),
                "modified_files": int(diff["modified_files"]),
                "deleted_files": int(diff["deleted_files"]),
            },
        }
        self.stages.append(stage)
        return stage

    def add_stage(
        self,
        name: str,
        status: str,
        duration_ms: int,
        scanned_count: int,
        generated_count: int,
        transfer_files: int,
        transfer_bytes: int,
        details: dict | None = None,
    ) -> None:
        self.stages.append(
            {
                "name": name,
                "status": status,
                "duration_ms": int(duration_ms),
                "scanned_count": int(scanned_count),
                "generated_count": int(generated_count),
                "transfer_files": int(transfer_files),
                "transfer_bytes": int(transfer_bytes),
                "details": details or {},
            }
        )

    def _load_previous_run(self) -> dict | None:
        if not os.path.isfile(self.log_path):
            return None
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except OSError:
            return None
        if not lines:
            return None
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            return None

    def finalize(self, success: bool) -> dict:
        ended_at = _iso_now()
        duration_ms = int((time.perf_counter() - self._started_ts) * 1000)
        totals = {
            "scanned_count": sum(stage["scanned_count"] for stage in self.stages),
            "generated_count": sum(stage["generated_count"] for stage in self.stages),
            "transfer_files": sum(stage["transfer_files"] for stage in self.stages),
            "transfer_bytes": sum(stage["transfer_bytes"] for stage in self.stages),
            "duration_ms": duration_ms,
        }

        payload: dict = {
            "schema": "imviewer.m06.metrics.v1",
            "pipeline": self.pipeline,
            "mode": self.mode,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "success": bool(success),
            "totals": totals,
            "stages": self.stages,
        }

        previous = self._load_previous_run()
        if previous and isinstance(previous, dict):
            prev_totals = previous.get("totals") if isinstance(previous.get("totals"), dict) else {}
            payload["compare"] = {
                "previous_run_id": previous.get("run_id"),
                "previous_started_at": previous.get("started_at"),
                "delta_duration_ms": int(totals["duration_ms"] - int(prev_totals.get("duration_ms", 0))),
                "delta_generated_count": int(totals["generated_count"] - int(prev_totals.get("generated_count", 0))),
                "delta_transfer_files": int(totals["transfer_files"] - int(prev_totals.get("transfer_files", 0))),
                "delta_transfer_bytes": int(totals["transfer_bytes"] - int(prev_totals.get("transfer_bytes", 0))),
            }

        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")
        return payload