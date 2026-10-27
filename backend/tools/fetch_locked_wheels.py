"""Fetch current-platform wheels with stdlib HTTP and lockfile SHA-256 verification.

The builder exports exact requirements from uv.lock first. No alternate versions or
unverified source archives are permitted. pip then installs offline with required hashes.
"""

import hashlib
import socket
import sys
import time
import tomllib
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import parse_wheel_filename

# Docker Desktop can advertise IPv6 routes that silently black-hole artifact traffic.
# Keep this preference local to the build downloader; TLS and hash checks remain enabled.
original_getaddrinfo = socket.getaddrinfo


def ipv4_addresses(*args, **kwargs):
    addresses = original_getaddrinfo(*args, **kwargs)
    return [item for item in addresses if item[0] == socket.AF_INET] or addresses


socket.getaddrinfo = ipv4_addresses

root, specification, destination = map(Path, sys.argv[1:])
destination.mkdir(parents=True, exist_ok=True)
locked = tomllib.loads((root / "uv.lock").read_text())
packages = {(p["name"], p["version"]): p for p in locked["package"]}
priorities = {tag: index for index, tag in enumerate(sys_tags())}
wheels = []
for line in specification.read_text().splitlines():
    if not line.strip() or line.lstrip().startswith("#"):
        continue
    requirement = Requirement(line)
    if requirement.marker and not requirement.marker.evaluate():
        continue
    versions = list(requirement.specifier)
    if len(versions) != 1 or versions[0].operator != "==":
        raise RuntimeError("Only exact locked requirements are permitted")
    package = packages[(requirement.name.lower().replace("_", "-"), versions[0].version)]
    candidates = []
    for wheel in package.get("wheels", []):
        filename = urllib.parse.unquote(wheel["url"].rsplit("/", 1)[1])
        compatible = parse_wheel_filename(filename)[3].intersection(priorities)
        if compatible:
            candidates.append((min(priorities[tag] for tag in compatible), filename, wheel))
    if not candidates:
        raise RuntimeError("No compatible locked wheel for " + requirement.name)
    wheels.append(min(candidates, key=lambda item: item[0]))


def fetch(item):
    _, filename, wheel = item
    url = urllib.parse.urlparse(wheel["url"])
    if url.scheme != "https" or url.hostname != "files.pythonhosted.org":
        raise RuntimeError("Unapproved package origin")
    expected = wheel["hash"].removeprefix("sha256:")
    expected_size = wheel["size"]
    target = destination / filename
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        return
    for attempt in range(4):
        try:
            # The only accepted scheme/host was checked above; no user-controlled URL.
            with urllib.request.urlopen(wheel["url"], timeout=30) as response:  # noqa: S310
                data = response.read(expected_size + 1)
            if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError("Locked wheel hash mismatch: " + filename)
            temporary = target.with_suffix(".part")
            temporary.write_bytes(data)
            temporary.replace(target)
            return
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


with ThreadPoolExecutor(max_workers=2) as executor:
    list(executor.map(fetch, wheels))
print(f"Verified {len(wheels)} locked wheels")
