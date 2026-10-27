"""Networkless supervisor: one bounded process per explicitly staged inspection job."""

import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from uuid import UUID


def main() -> None:
    source, destination = Path("/jobs/in"), Path("/jobs/out")
    while True:
        for marker in source.glob("*.cleanup"):
            try:
                job = str(UUID(marker.stem))
                directory = destination / job
                if directory.is_dir() and directory.resolve().parent == destination.resolve():
                    shutil.rmtree(directory)
                (destination / (job + ".result.json")).unlink(missing_ok=True)
            except (ValueError, OSError):
                continue
        for request in sorted(source.glob("*.json")):
            try:
                job = str(UUID(request.stem))
            except ValueError:
                continue
            result = destination / (job + ".result.json")
            if result.exists():
                continue
            with suppress(subprocess.TimeoutExpired):
                subprocess.run(  # noqa: S603 -- fixed interpreter/module and validated UUID.
                    [sys.executable, "-m", "workbench.processing.inspect_file", job],
                    env={
                        "PATH": "/usr/local/bin",
                        "LD_LIBRARY_PATH": "/usr/local/lib",
                        "PYTHONDONTWRITEBYTECODE": "1",
                        "PYTHONUNBUFFERED": "1",
                    },
                    cwd="/tmp",  # noqa: S108 -- private, size-limited container tmpfs.
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
            if not result.exists():
                temporary = result.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps({"status": "REJECTED", "reason": "PARSER_TIMEOUT_OR_RESOURCE_LIMIT"})
                )
                os.replace(temporary, result)
        time.sleep(0.2)


if __name__ == "__main__":
    main()
