"""Command-line interface for the AICTE Evidence Workbench.
Includes offline replay verifier: `workbench replay <bundle_file.json>`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from workbench.modules.rule_governance.service import RuleGovernanceService


def replay_command(bundle_path: Path) -> int:
    """Offline verification of an exported replay bundle.
    Does not contact database or network. Checks every hash.
    Exits non-zero and outputs failing hash name if any byte is altered.
    """
    if not bundle_path.exists():
        sys.stderr.write(f"Error: Bundle file not found at '{bundle_path}'\n")
        return 2

    try:
        with bundle_path.open("r", encoding="utf-8") as f:
            bundle_data = json.load(f)
    except Exception as exc:
        sys.stderr.write(f"Error parsing bundle JSON: {exc}\n")
        return 2

    success, error_msg = RuleGovernanceService.verify_replay_bundle_offline(bundle_data)
    if not success:
        sys.stderr.write(f"REPLAY_VERIFICATION_FAILED: {error_msg}\n")
        return 1

    disclaimer = bundle_data.get("disclaimer", "")
    if "does not reproduce a fresh OCR run" not in disclaimer:
        sys.stderr.write(
            "REPLAY_VERIFICATION_FAILED: Mandatory OCR limitation disclaimer missing\n"
        )
        return 1

    manifest = bundle_data.get("manifest", {})
    files = bundle_data.get("files", {})

    sys.stdout.write("REPLAY_VERIFICATION_SUCCESS: All bundle hashes match canonically.\n")
    sys.stdout.write(f"Bundle ID: {manifest.get('bundle_id')}\n")
    sys.stdout.write(f"Run ID: {manifest.get('run_id')}\n")
    sys.stdout.write(f"Evaluator Version: {manifest.get('evaluator_version')}\n")
    sys.stdout.write(f"Verified Files ({len(files)}): {', '.join(files.keys())}\n")
    sys.stdout.write(f"Notice: {disclaimer}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workbench", description="AICTE Workbench CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    replay_parser = subparsers.add_parser("replay", help="Verify offline reproducibility bundle")
    replay_parser.add_argument("bundle", type=Path, help="Path to exported bundle JSON")

    args = parser.parse_args(argv)
    if args.command == "replay":
        return replay_command(args.bundle)

    return 0


if __name__ == "__main__":
    sys.exit(main())
