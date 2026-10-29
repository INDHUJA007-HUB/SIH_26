#!/usr/bin/env python3
"""Secret scan guard to detect credentials, keys, and improperly tracked files."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Patterns to detect
AKIA_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")
# Matches URI credentials scheme://user:token@host
URL_CRED_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^:\s@/?#]+:([^@\s/?#]+)@[^\s\"'`<>]+")

# Placeholders or environment variables that are safe in URLs
SAFE_PASSWORD_TOKENS = {
    "<password>",
    "<REDACTED>",
    "ephemeral-ci-only",
}


def is_safe_url_password(pw: str) -> bool:
    if not pw:
        return True
    if pw in SAFE_PASSWORD_TOKENS:
        return True
    # Templated variables like ${POSTGRES_PASSWORD} or {password} or <...>
    if pw.startswith("${") and pw.endswith("}"):
        return True
    if pw.startswith("{") and pw.endswith("}"):
        return True
    if pw.startswith("<") and pw.endswith(">"):
        return True
    return False


def check_tracked_files() -> list[str]:
    git_bin = shutil.which("git")
    if not git_bin:
        return ["Git executable not found"]
    
    result = subprocess.run(
        [git_bin, "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return [f"git ls-files failed: {result.stderr}"]
    
    violations = []
    for line in result.stdout.splitlines():
        rel_path = line.strip()
        name = Path(rel_path).name
        # Check for tracked .tfvars files (excluding .example)
        if name.endswith(".tfvars") and not name.endswith(".tfvars.example"):
            violations.append(f"Tracked tfvars file: {rel_path}")
        # Check for tracked .env files (excluding .example)
        if (name == ".env" or name.startswith(".env.")) and not name.endswith(".example"):
            violations.append(f"Tracked .env file: {rel_path}")
            
    return violations


def check_file_contents() -> list[str]:
    git_bin = shutil.which("git")
    if not git_bin:
        return ["Git executable not found"]
    
    # Check tracked and untracked (non-ignored) files
    result = subprocess.run(
        [git_bin, "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return [f"git ls-files failed: {result.stderr}"]
    
    violations = []
    scanned_suffixes = {
        ".py", ".md", ".json", ".yml", ".yaml", ".toml", ".ps1", ".sh", ".tf", ".tfvars",
        ".txt", ".rst", ".sql", ".conf", ".ini", ".env", ".example"
    }

    for rel_path in result.stdout.splitlines():
        rel_path = rel_path.strip()
        fpath = ROOT / rel_path
        if not fpath.is_file():
            continue
        if fpath.name == "check_secrets.py":
            continue
        if fpath.suffix.lower() not in scanned_suffixes and not fpath.name.startswith(".env"):
            continue
        
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            continue
        
        for line_no, line in enumerate(content.splitlines(), start=1):
            # Check AKIA
            if AKIA_PATTERN.search(line):
                violations.append(f"AWS Access Key pattern at {rel_path}:{line_no}")
            # Check Private Key
            if PRIVATE_KEY_PATTERN.search(line):
                violations.append(f"Private Key header pattern at {rel_path}:{line_no}")
            # Check URL credentials
            for m in URL_CRED_PATTERN.finditer(line):
                pw = m.group(1)
                if not is_safe_url_password(pw):
                    violations.append(f"Password-bearing URL pattern at {rel_path}:{line_no}")

    return violations


def main() -> int:
    print("=" * 70)
    print("RUNNING WORKBENCH SECRET-SCAN GUARD (scripts/check_secrets.py)")
    print("=" * 70)
    
    tracked_violations = check_tracked_files()
    content_violations = check_file_contents()
    
    all_violations = tracked_violations + content_violations
    if all_violations:
        print(f"FAILED: Found {len(all_violations)} security violation(s):")
        for v in all_violations:
            print(f"  [VIOLATION] {v}")
        return 1
    
    print("PASS: No password-bearing URLs, AKIA keys, private keys, or tracked .tfvars/.env files found.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
