"""Network and webhook security guards (OWASP API Top 10 compliance).

Provides:
- Outbound URL and SSRF validation (loopback, private ranges, link-local, metadata)
- Webhook HMAC signature verification and timestamp replay rejection
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import socket
import time
from urllib.parse import urlparse

# Prohibited CIDR blocks for outbound connectors / URL references
PROHIBITED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback IPv4
    ipaddress.ip_network("10.0.0.0/8"),  # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / AWS metadata
    ipaddress.ip_network("::1/128"),  # Loopback IPv6
    ipaddress.ip_network("fe80::/10"),  # Link-local IPv6
    ipaddress.ip_network("fc00::/7"),  # Unique local address (IPv6 private)
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast IPv4
    ipaddress.ip_network("ff00::/8"),  # Multicast IPv6
]

# Government approved domain suffixes for statutory connectors
APPROVED_GOVERNMENT_DOMAINS = [
    "aicte-india.org",
    "gov.in",
    "nic.in",
    "digilocker.gov.in",
    "tn.gov.in",
    "karnataka.gov.in",
    "maharashtra.gov.in",
]


class SSRFValidationError(ValueError):
    """Raised when an outbound URL violates SSRF or private network constraints."""


class WebhookVerificationError(ValueError):
    """Raised when a webhook fails signature verification, timestamp freshness, or replay checks."""


def is_ip_prohibited(ip_str: str) -> bool:
    """Check if an IP address falls into a prohibited (private, loopback, link-local) network."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return any(ip in net for net in PROHIBITED_NETWORKS)


def validate_outbound_url(
    url: str,
    allowlist_domains: list[str] | None = None,
    allow_private_in_test: bool = False,
) -> tuple[bool, str]:
    """Validate that an outbound URL does not target loopback, private, or prohibited addresses.

    Returns (is_valid, reason).
    """
    if not url:
        return False, "URL is empty"

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Prohibited scheme: {parsed.scheme} (only http and https allowed)"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"

    hostname_lower = hostname.lower()

    # Block well-known metadata or local names directly
    if hostname_lower in ("localhost", "metadata", "instance-data", "169.254.169.254"):
        return False, f"Prohibited hostname: {hostname}"

    # Check domain allowlist if specified
    if allowlist_domains is not None:
        matched = any(
            hostname_lower == d or hostname_lower.endswith("." + d) for d in allowlist_domains
        )
        if not matched:
            return False, f"Hostname '{hostname}' not in approved allowlist"

    # Resolve IP address to prevent DNS rebinding to internal IP
    if not allow_private_in_test:
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            resolved_ips = {str(item[4][0]) for item in addr_info}
        except socket.gaierror:
            return False, f"Cannot resolve hostname: {hostname}"

        for ip_str in resolved_ips:
            if is_ip_prohibited(ip_str):
                return (
                    False,
                    f"Resolved IP {ip_str} for host '{hostname}' is in a prohibited network",
                )

    return True, "URL is safe and allowed"


# In-memory replay cache for webhook replay protection: (replay_id, timestamp)
_SEEN_REPLAY_IDS: dict[str, float] = {}


def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> tuple[bool, str]:
    """Verify an incoming webhook payload using HMAC-SHA256 and timestamp replay protection.

    Expected signature header format:
        t=<unix_timestamp>,v1=<hex_hmac_sha256>,id=<optional_replay_id>

    Returns (is_valid, reason).
    """
    if not signature_header:
        return False, "Missing signature header"

    parts = {}
    for item in signature_header.split(","):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            parts[k] = v

    ts_str = parts.get("t")
    sig = parts.get("v1")
    replay_id = parts.get("id")

    if not ts_str or not sig:
        return False, "Malformed signature header (requires t= and v1=)"

    try:
        timestamp = float(ts_str)
    except ValueError:
        return False, "Invalid timestamp in signature header"

    now = time.time()
    if abs(now - timestamp) > tolerance_seconds:
        delta = abs(now - timestamp)
        return (
            False,
            f"Webhook timestamp expired or in future (delta {delta:.1f}s > {tolerance_seconds}s)",
        )

    # Check replay cache
    cache_key = replay_id or f"{ts_str}:{sig}"
    clean_seen_replays(now, tolerance_seconds)
    if cache_key in _SEEN_REPLAY_IDS:
        return (
            False,
            f"Replay detected: webhook ID or signature '{cache_key}' has already been processed",
        )

    # Compute expected signature: HMAC-SHA256(secret, f"{t}.{payload}")
    signed_payload = f"{ts_str}.".encode() + payload_bytes
    expected_sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig.lower(), expected_sig.lower()):
        return False, "Invalid HMAC signature"

    # Record replay ID
    _SEEN_REPLAY_IDS[cache_key] = now
    return True, "Webhook signature and timestamp verified"


def clean_seen_replays(now: float, tolerance_seconds: int) -> None:
    """Evict replay IDs older than tolerance window."""
    expired = [k for k, t in _SEEN_REPLAY_IDS.items() if now - t > tolerance_seconds * 2]
    for k in expired:
        _SEEN_REPLAY_IDS.pop(k, None)
