"""Offline verification: no OpenAI calls, no model downloads, no production DB truncation."""

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    ["uv", "run", "ruff", "check", "backend", "tests", "scripts"],
    ["uv", "run", "pytest", "-q"],
    ["npm", "--prefix", "frontend", "run", "typecheck"],
    ["uv", "run", "python", "-m", "lovecode.dataset", "validate"],
    ["uv", "run", "python", "-m", "lovecode.annotate", "--dry-run"],
    ["uv", "run", "python", "-m", "lovecode.train", "--allow-ai-drafts", "--dry-run"],
    ["uv", "run", "python", "-m", "lovecode.experiment", "--dry-run"],
    ["uv", "run", "python", "-m", "lovecode.pipeline", "--dry-run"],
]


def main():
    reports = []
    for command in COMMANDS:
        start = time.monotonic()
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        report = {
            "command": " ".join(command),
            "exit_code": p.returncode,
            "seconds": round(time.monotonic() - start, 3),
        }
        if p.returncode == 0:
            report["output"] = p.stdout.strip()
        else:
            report["output"] = "Failed; rerun this command locally for details."
        reports.append(report)
        print(("PASS" if p.returncode == 0 else "FAIL") + " " + report["command"])
    dest = ROOT / "artifacts/reports/offline-verification.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "executed_at": datetime.now(UTC).isoformat(),
                "paid_api_calls": 0,
                "production_training_executed": False,
                "fixture_training_executed": any(
                    r["command"] == "uv run pytest -q" and r["exit_code"] == 0 for r in reports
                ),
                "checks": reports,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    raise SystemExit(any(r["exit_code"] for r in reports))


if __name__ == "__main__":
    main()
