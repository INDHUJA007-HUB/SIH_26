"""Scan tracked/new nonignored files for high-risk credential formats without printing values."""

import shutil
import subprocess
from pathlib import Path

from detect_secrets import SecretsCollection
from detect_secrets.settings import transient_settings

ROOT = Path(__file__).resolve().parents[2]
git_executable = shutil.which("git")
if git_executable is None:
    raise SystemExit("Git is required for credential scanning")
files = (
    subprocess.check_output(  # noqa: S603 -- resolved Git executable; fixed literal arguments only.
        [git_executable, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    .decode()
    .split("\0")
)
plugins = ["AWSKeyDetector", "GitHubTokenDetector", "PrivateKeyDetector", "JwtTokenDetector"]
with transient_settings({"plugins_used": [{"name": name} for name in plugins]}):
    found = SecretsCollection()
    for name in files:
        path = ROOT / name
        if path.is_file() and path.suffix in {
            ".py",
            ".md",
            ".json",
            ".yml",
            ".yaml",
            ".toml",
            ".ps1",
            ".sh",
        }:
            found.scan_file(str(path))
    findings = found.json()
if findings:
    for filename, matches in findings.items():
        for finding in matches:
            print(
                f"Credential pattern: {Path(filename).relative_to(ROOT)}:{finding['line_number']}"
            )
    raise SystemExit(1)
print("High-risk credential-format scan: PASS (values are never printed)")
