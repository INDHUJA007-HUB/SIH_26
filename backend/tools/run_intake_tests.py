"""Run local stack acceptance without printing database credentials."""

import argparse
import os
import shutil
from pathlib import Path

import pytest

from workbench.platform.config import PROJECT_ROOT, Settings

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--failure-probes",
    action="store_true",
    help="Include temporary local parser/relay stop and recovery probes",
)
arguments, pytest_arguments = parser.parse_known_args()
settings = Settings()
if settings.environment not in {"local", "test"}:
    raise SystemExit("Acceptance fixtures are restricted to local/test environments")
url = settings.database_url.get_secret_value()
if not url:
    raise SystemExit("Run local bootstrap and migrations before stack acceptance")
os.environ["WB_INTEGRATION_DATABASE_URL"] = url
os.environ["WB_FILE_INTEGRATION"] = "1"
if arguments.failure_probes:
    os.environ["WB_CHAOS_INTEGRATION"] = "1"
if os.name == "nt" and shutil.which("docker") is None:
    docker = Path(os.environ["LOCALAPPDATA"]) / "Programs/DockerDesktop/resources/bin"
    if (docker / "docker.exe").is_file():
        os.environ["PATH"] = str(docker) + os.pathsep + os.environ["PATH"]
raise SystemExit(pytest.main([str(PROJECT_ROOT / "backend/tests"), *pytest_arguments]))
