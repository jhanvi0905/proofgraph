"""Offline CLI. The detention fixture never calls Muse."""

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETENTION_REASON = (
    "Detention should be $165.00, not $450.00 (4.2 h on site, 2 h free, $75/h)"
)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MODEL_API_KEY", None)
    env.pop("BASETEN_API_KEY", None)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_detention_fixture_prints_verdict_label_and_reasons():
    result = subprocess.run(
        [sys.executable, "-m", "proofgraph", "tests/fixtures/detention_program.json"],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "CONTRADICTED",
        "COMPUTED",
        DETENTION_REASON,
    ]


def test_cli_does_not_import_muse_or_the_proposer():
    tree = ast.parse((ROOT / "proofgraph" / "__main__.py").read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    for name in modules:
        assert "muse" not in name.split(".")
        assert "propose" not in name
        assert "checker" not in name
        assert "openai" not in name
