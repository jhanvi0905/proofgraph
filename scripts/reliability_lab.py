"""Offline discovery experiments. No product imports, secrets, or external calls.

These are controlled fixtures and fault injections, not a customer study or an
availability benchmark. Ground-truth labels are never passed to the explainer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile
import time


RULES = (
    ("code", r"^(?:AssertionError|SyntaxError|TypeError|NameError):", "Inspect the failing code or test before rerunning."),
    ("runner", r"^The runner has lost communication with the server\.$", "Check runner health; confirm replay safety before retrying."),
    ("dependency", r"^ERROR: (?:Could not resolve host|No matching distribution found)", "Check the external dependency and version constraints."),
    ("configuration", r"^(?:Error: Required secret .+ is not set|PermissionError: .+|Error: Resource not accessible by integration)$", "Check configuration and permissions; a rerun alone may not help."),
)


def explain(log: str) -> dict:
    """Conservative baseline: retain evidence and abstain on mixed signals."""
    evidence = []
    for number, line in enumerate(log.splitlines(), 1):
        for category, pattern, action in RULES:
            if re.search(pattern, line):
                evidence.append({"line": number, "text": line, "category": category, "next_action": action})
    categories = {item["category"] for item in evidence}
    category = next(iter(categories)) if len(categories) == 1 else "unknown"
    return {"category": category, "evidence": evidence,
            "next_action": evidence[0]["next_action"] if category != "unknown" else "Inspect more evidence; do not assume this is safe to retry."}


def diagnosis_experiment() -> dict:
    # Explicit adversarial/ambiguous cases prevent a generic 'timeout = infra' rule.
    fixtures = [
        ("assertion", "Running test_total\nAssertionError: expected 4, got 5", "code"),
        ("syntax", "SyntaxError: invalid syntax", "code"),
        ("type", "TypeError: unsupported operand", "code"),
        ("name", "NameError: missing_function", "code"),
        ("runner_disconnect", "The runner has lost communication with the server.", "runner"),
        ("dns", "ERROR: Could not resolve host registry.example.invalid", "dependency"),
        ("package_version", "ERROR: No matching distribution found for imaginary-package==0", "dependency"),
        ("secret", "Error: Required secret DEMO_KEY is not set", "configuration"),
        ("permissions", "PermissionError: access denied", "configuration"),
        ("token_scope", "Error: Resource not accessible by integration", "configuration"),
        ("timeout_ambiguous", "Task exceeded timeout of 30 seconds", "unknown"),
        ("exit_one", "Process completed with exit code 1", "unknown"),
        ("no_logs", "", "unknown"),
        ("quoted_error", "Example of an error: AssertionError: expected 4", "unknown"),
        ("two_causes", "AssertionError: bad output\nThe runner has lost communication with the server.", "unknown"),
        ("network_app", "Application request timed out", "unknown"),
    ]
    cases = []
    for case_id, log, expected in fixtures:
        result = explain(log)
        assert result["category"] == expected, (case_id, result)
        for item in result["evidence"]:
            assert log.splitlines()[item["line"] - 1] == item["text"]
        cases.append({"id": case_id, "source": "constructed_fixture", "log": log,
                      "expected": expected, "explanation": result})
    classified = [case for case in cases if case["explanation"]["category"] != "unknown"]
    return {"source": "constructed_fixtures", "cases": cases, "metrics": {
        "fixture_cases": len(cases), "correct_including_abstentions": len(cases),
        "classified": len(classified), "abstained": len(cases) - len(classified),
        "evidence_line_checks": sum(len(case["explanation"]["evidence"]) for case in cases),
        "human_diagnosis_time": None, "historical_generalization": "not_measured"}}


def worker(db: Path, scenario: str, attempt: int, safe: bool, key: str) -> int:
    """A real local transaction with injected pre-write and post-commit errors."""
    if scenario == "permanent":
        print("Permanent input error; do not retry.")
        return 2
    if scenario == "exhausted" or (scenario == "transient" and attempt < 3):
        print("Injected temporary error before the operation.")
        return 75
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS effects (operation_key TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS completed (operation_key TEXT PRIMARY KEY)")
        exists = connection.execute("SELECT 1 FROM completed WHERE operation_key = ?", (key,)).fetchone()
        if not safe or not exists:
            connection.execute("INSERT INTO effects VALUES (?)", (key,))
            connection.execute("INSERT OR IGNORE INTO completed VALUES (?)", (key,))
    if scenario == "lost_ack" and attempt == 1:
        print("Injected lost response after committed operation.")
        return 75
    print("Operation acknowledged.")
    return 0


def run_operation(root: Path, scenario: str, safe: bool, operation: str) -> dict:
    db = root / f"{operation}.sqlite"
    started = time.monotonic()
    attempts = []
    wait_seconds = 0.0
    for attempt in range(1, 4):
        task = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker",
                               "--db", str(db), "--scenario", scenario,
                               "--attempt", str(attempt), "--key", operation,
                               *( ["--safe"] if safe else [])], capture_output=True, text=True, timeout=10)
        attempts.append({"attempt": attempt, "exit_code": task.returncode, "output": task.stdout.strip()})
        if task.returncode != 75 or attempt == 3:
            break
        delay = 0.01 * 2 ** (attempt - 1)
        wait_seconds += delay
        time.sleep(delay)
    effects = 0
    if db.exists():
        with sqlite3.connect(db) as connection:
            effects = connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
    return {"operation": operation, "scenario": scenario, "safe": safe,
            "attempts": attempts, "success": attempts[-1]["exit_code"] == 0,
            "effects": effects, "duplicates": max(0, effects - 1),
            "retry_wait_seconds": wait_seconds, "wall_seconds": time.monotonic() - started}


def recovery_experiment() -> dict:
    operations = []
    with tempfile.TemporaryDirectory() as directory:
        for repeat in range(4):
            for scenario, safe in [("lost_ack", False), ("lost_ack", True),
                                   ("transient", True), ("permanent", True), ("exhausted", True)]:
                operation = f"{scenario}-{safe}-{repeat}"
                result = run_operation(Path(directory), scenario, safe, operation)
                if scenario == "lost_ack":
                    assert result["success"] and result["effects"] == (1 if safe else 2)
                elif scenario == "transient":
                    assert result["success"] and result["effects"] == 1 and len(result["attempts"]) == 3
                elif scenario == "permanent":
                    assert not result["success"] and len(result["attempts"]) == 1 and result["effects"] == 0
                else:
                    assert not result["success"] and len(result["attempts"]) == 3 and result["effects"] == 0
                operations.append(result)
    recoverable_safe = [r for r in operations if r["safe"] and r["scenario"] in {"lost_ack", "transient"}]
    return {"source": "local_subprocess_fault_injection", "operations": operations, "metrics": {
        "operations": len(operations), "recoverable_safe_operations": len(recoverable_safe),
        "recovered_safe_operations": sum(r["success"] for r in recoverable_safe),
        "naive_duplicate_effects": sum(r["duplicates"] for r in operations if not r["safe"]),
        "safe_duplicate_effects": sum(r["duplicates"] for r in operations if r["safe"]),
        "permanent_cases_stopped_after_one_attempt": sum(r["scenario"] == "permanent" and len(r["attempts"]) == 1 for r in operations),
        "bounded_exhaustion_cases": sum(r["scenario"] == "exhausted" and len(r["attempts"]) == 3 for r in operations),
        "subprocess_attempts": sum(len(r["attempts"]) for r in operations),
        "wall_seconds": sum(r["wall_seconds"] for r in operations),
        "production_replay_safety": "not_measured"}}


def reconcile(expected: dict, observed: list[dict], now: int, snapshot_age: int = 0,
              readable: bool = True) -> str:
    if not readable or snapshot_age > 60:
        return "unknown"
    if not expected["eligible"]:
        return "not_expected"
    matches = [run for run in observed if run["key"] == expected["key"]]
    if matches:
        latest = max(matches, key=lambda run: run.get("attempt", 1))
        status = latest["status"]
        return {"queued": "waiting", "pending": "waiting", "waiting": "blocked",
                "in_progress": "running", "completed": "completed", "cancelled": "cancelled",
                "skipped": "skipped"}.get(status, "unknown")
    return "missing" if now >= expected["deadline"] else "not_due"


def missing_experiment() -> dict:
    expected = {"key": "commit-123:test-workflow", "eligible": True, "deadline": 120}
    def run(status: str, key: str = expected["key"], attempt: int = 1) -> dict:
        return {"key": key, "status": status, "attempt": attempt}
    fixtures = [
        ("before_deadline", expected, [], 90, 0, True, "not_due"),
        ("at_deadline", expected, [], 120, 0, True, "missing"),
        ("after_deadline", expected, [], 180, 0, True, "missing"),
        ("unrelated_run", expected, [run("completed", "different-workflow")], 180, 0, True, "missing"),
        ("waiting", expected, [run("queued")], 180, 0, True, "waiting"),
        ("pending", expected, [run("pending")], 180, 0, True, "waiting"),
        ("approval", expected, [run("waiting")], 180, 0, True, "blocked"),
        ("running", expected, [run("in_progress")], 180, 0, True, "running"),
        ("done", expected, [run("completed")], 180, 0, True, "completed"),
        ("cancelled", expected, [run("cancelled")], 180, 0, True, "cancelled"),
        ("skipped", expected, [run("skipped")], 180, 0, True, "skipped"),
        ("stale", expected, [], 180, 61, True, "unknown"),
        ("permission_denied", expected, [], 180, 0, False, "unknown"),
        ("filtered", {**expected, "eligible": False}, [], 180, 0, True, "not_expected"),
        ("rerun", expected, [run("completed"), run("in_progress", attempt=2)], 180, 0, True, "running"),
    ]
    results = []
    for case_id, obligation, observations, now, age, readable, truth in fixtures:
        state = reconcile(obligation, observations, now, age, readable)
        assert state == truth, (case_id, state, truth)
        results.append({"id": case_id, "expected": truth, "actual": state})
    # Independent polling schedules include different phases; virtual time avoids a long wait.
    detections = []
    for deadline in [120, 137, 179, 211]:
        for phase in [0, 7, 29]:
            obligation = {**expected, "deadline": deadline}
            seen = next(t for t in range(phase, deadline + 31, 30)
                        if reconcile(obligation, [], t) == "missing")
            detections.append({"deadline": deadline, "poll_phase": phase, "detected": seen,
                               "delay_seconds": seen - deadline})
    assert all(0 <= item["delay_seconds"] < 30 for item in detections)
    negative_cases = [r for r in results if r["expected"] != "missing"]
    return {"source": "constructed_states_and_virtual_clock", "cases": results,
            "detections": detections, "metrics": {
                "state_cases": len(results), "correct_states": len(results),
                "missing_cases": len(results) - len(negative_cases),
                "negative_cases": len(negative_cases),
                "false_missing_alerts": sum(r["actual"] == "missing" for r in negative_cases),
                "polling_scenarios": len(detections),
                "max_simulated_detection_delay_seconds": max(d["delay_seconds"] for d in detections),
                "real_github_detection_latency": None}}


def probe(kind: str) -> int:
    print(f"Controlled reliability probe: {kind}; not a product defect.", flush=True)
    if kind == "code":
        try:
            assert 2 + 2 == 5, "injected calculation bug: expected 5, got 4"
        except AssertionError as error:
            print(f"AssertionError: {error}", flush=True)
            return 1
    if kind == "transient" and int(os.getenv("GITHUB_RUN_ATTEMPT", "1")) == 1:
        print("Injected temporary failure on first workflow attempt; retry is safe (no side effects).", flush=True)
        return 75
    print("Probe completed successfully.", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/reliability-lab"))
    parser.add_argument("--probe", choices=["code", "transient"])
    parser.add_argument("--diagnose-log", type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--scenario")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--key", default="demo")
    parser.add_argument("--safe", action="store_true")
    args = parser.parse_args()
    if args.diagnose_log:
        print(json.dumps(explain(args.diagnose_log.read_text()), indent=2))
        return 0
    if args.probe:
        return probe(args.probe)
    if args.worker:
        return worker(args.db, args.scenario, args.attempt, args.safe, args.key)
    results = {"evidence_type": "controlled_experiments_not_customer_validation",
               "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
               "python": platform.python_version(), "platform": platform.platform(),
               "github_sha": os.getenv("GITHUB_SHA"), "github_run_id": os.getenv("GITHUB_RUN_ID"),
               "diagnosis": diagnosis_experiment(), "recovery": recovery_experiment(),
               "missing": missing_experiment()}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    lines = ["# Reliability lab: controlled experiment results", "",
             "Synthetic fixtures, real local transactions, and simulated clocks. Human benefit and production reliability remain unmeasured.", ""]
    for name in ("diagnosis", "recovery", "missing"):
        lines += [f"## {name}", "", "```json", json.dumps(results[name]["metrics"], indent=2), "```", ""]
    (args.output / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
