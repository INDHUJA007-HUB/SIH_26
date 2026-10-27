"""Run the foundation quality gates with explicit failure propagation and evidence output."""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime

from workbench.platform.config import PROJECT_ROOT, Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    environment = os.environ.copy()
    if args.integration:
        environment["WB_INTEGRATION_DATABASE_URL"] = Settings().database_url.get_secret_value()
    commands = [
        ["-m", "ruff", "check", "src", "tests", "tools", "migrations"],
        ["-m", "ruff", "format", "--check", "src", "tests", "tools", "migrations"],
        ["-m", "mypy"],
        ["tools/check_architecture.py"],
        ["tools/check_repository.py"],
        ["tools/check_secrets.py"],
        ["-m", "pytest", "-q", "--tb=short", "--junitxml=../artifacts/tests.xml"],
    ]
    records = []
    for arguments in commands:
        completed = subprocess.run(  # noqa: S603 -- interpreter and command arguments are fixed.
            [sys.executable, *arguments],
            cwd=PROJECT_ROOT / "backend",
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        records.append(
            {
                "command": "python " + " ".join(arguments),
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        print(records[-1]["command"], "PASS" if completed.returncode == 0 else "FAIL")
        if completed.returncode:
            print(completed.stdout, completed.stderr)
            break
    destination = PROJECT_ROOT / "artifacts/verification.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "executed_at": datetime.now(UTC).isoformat(),
                "integration_requested": args.integration,
                "checks": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if any(record["returncode"] for record in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
