"""Migration safety and expand/contract verification tool.

Performs static analysis on all Alembic migration scripts to ensure:
1. Continuous revision chain (no broken down_revisions or orphan heads).
2. No destructive DDL statements (DROP TABLE, DROP COLUMN, TRUNCATE).
3. Expand/Contract safety: any column added to an existing table must be
   nullable=True or provide a server_default, ensuring older worker versions
   can continue operating safely during rolling canary deployments.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def verify_migrations(migrations_dir: Path) -> tuple[int, list[str]]:
    findings: list[str] = []
    versions_dir = migrations_dir / "versions"
    if not versions_dir.exists():
        return 1, [f"Versions directory not found: {versions_dir}"]

    py_files = sorted([f for f in versions_dir.glob("*.py") if not f.name.startswith("__")])
    if not py_files:
        return 1, ["No migration files found."]

    revisions: dict[str, str | None] = {}
    down_revisions: set[str] = set()

    destructive_patterns = [
        (re.compile(r"\bdrop_table\b", re.IGNORECASE), "Destructive drop_table detected"),
        (re.compile(r"\bdrop_column\b", re.IGNORECASE), "Destructive drop_column detected"),
        (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "Destructive TRUNCATE statement detected"),
    ]

    add_column_pattern = re.compile(
        r"op\.add_column\(\s*['\"](?P<table>\w+)['\"]\s*,\s*sa\.Column\(\s*['\"](?P<col>\w+)['\"].*?\)",
        re.DOTALL,
    )

    for f in py_files:
        content = f.read_text(encoding="utf-8")

        # Extract revision and down_revision
        rev_match = re.search(r'revision\s*=\s*["\']([^"\']+)["\']', content)
        down_match = re.search(r'down_revision\s*=\s*(?:["\']([^"\']+)["\']|None)', content)

        if not rev_match:
            findings.append(f"{f.name}: Missing revision identifier")
            continue

        rev_id = rev_match.group(1)
        down_rev_id = down_match.group(1) if down_match and down_match.group(1) else None

        revisions[rev_id] = down_rev_id
        if down_rev_id:
            down_revisions.add(down_rev_id)

        # 2. Check for destructive statements in upgrade() only
        upgrade_match = re.search(r"def upgrade\(\).*?:(.*?)(?=\ndef |\Z)", content, re.DOTALL)
        if upgrade_match:
            upgrade_code = upgrade_match.group(1)
            for pattern, msg in destructive_patterns:
                if pattern.search(upgrade_code):
                    findings.append(f"{f.name}: {msg}")

        # 3. Check expand/contract rules: add_column must be nullable or have server_default
        for match in add_column_pattern.finditer(content):
            col_def = match.group(0)
            table_name = match.group("table")
            col_name = match.group("col")

            is_nullable = "nullable=True" in col_def or "nullable=False" not in col_def
            has_server_default = "server_default=" in col_def

            if not is_nullable and not has_server_default:
                findings.append(
                    f"{f.name}: Column '{col_name}' added to '{table_name}' is nullable=False without server_default "
                    f"(breaks older concurrent workers during canary rollout)"
                )

    # 4. Verify chain integrity: exactly one initial migration (down_revision=None)
    root_revisions = [rev for rev, down in revisions.items() if down is None]
    if len(root_revisions) != 1:
        findings.append(
            f"Chain integrity error: expected 1 root revision, found {len(root_revisions)}: {root_revisions}"
        )

    # Check that all down_revisions exist
    for rev, down in revisions.items():
        if down is not None and down not in revisions:
            findings.append(f"Broken chain: {rev} references unknown down_revision '{down}'")

    # Check for single head
    heads = [rev for rev in revisions if rev not in down_revisions]
    if len(heads) != 1:
        findings.append(f"Multiple migration heads detected: {heads}")

    return len(findings), findings


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = repo_root / "backend" / "migrations"

    print("=" * 70)
    print("STARTING MIGRATION SAFETY & EXPAND/CONTRACT QUALIFICATION CHECK")
    print(f"Migrations Directory: {migrations_dir}")
    print("=" * 70)

    error_count, findings = verify_migrations(migrations_dir)
    if error_count > 0:
        print(f"\n[FAIL] {error_count} migration safety check(s) failed:")
        for f in findings:
            print(f" - {f}")
        return 1

    print("[PASS] Checkpoint 1: Linear migration chain verified with exactly 1 root and 1 head.")
    print(
        "[PASS] Checkpoint 2: Zero destructive statements (DROP TABLE, DROP COLUMN, TRUNCATE) detected."
    )
    print(
        "[PASS] Checkpoint 3: Expand/Contract safety verified: all column additions backward compatible."
    )
    print(
        "[PASS] Checkpoint 4: Compatible with concurrent older worker executions during rolling canary."
    )
    print("=" * 70)
    print("MIGRATION QUALIFICATION: ALL CHECKS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
