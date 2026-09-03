"""SSRF guard for outbound fetches of untrusted URLs (R0-03 / audit U-14).

Every URL derived from lead data or scraped pages is checked here before any
HTTP request is made. The validator:

1. allows only ``http``/``https`` schemes (``file://``, ``gopher://``, ... die here);
2. rejects hostnames that resolve to private, loopback, link-local, multicast,
   reserved or unspecified addresses (IPv4 and IPv6), including literal IPs;
3. resolves DNS itself and re-checks every returned A/AAAA record, so a public
  -looking hostname pointing at ``10.x.x.x`` is caught.

Residual risk (documented, not claimed as solved): the target may re-resolve
to an internal address *between* this check and the actual connect (DNS
rebinding TOCTOU). Fully closing it requires pinning the validated IP in the
HTTP client's transport (planned for R2-01's shared ``http_client.py``).

The resolver is injectable for tests. Behavior is gated by the
``ENRICH_SSRF_GUARD`` env var (default **on** — a deliberate exception to the
repo's all-flags-default-False convention: this is a security invariant, not a
new capability; an off-by-default guard protects nothing).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_RESOLVE_TIMEOUT = 5.0

_SCHEME_ALLOWLIST = {"http", "https"}


class SSRFBlockedError(ValueError):
    """Raised when a URL fails the SSRF guard."""


@dataclass
class SSRFDecision:
    """Result of validating one URL."""

    allowed: bool
    reason: str
    resolved_ips: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.allowed


def ssrf_guard_enabled() -> bool:
    """Whether the SSRF guard is active (``ENRICH_SSRF_GUARD``, default on)."""
    return os.environ.get("ENRICH_SSRF_GUARD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Return a rejection reason for private/reserved addresses, else None."""
    if ip.is_private:
        return f"private address {ip}"
    if ip.is_loopback:
        return f"loopback address {ip}"
    if ip.is_link_local:
        return f"link-local address {ip}"
    if ip.is_multicast:
        return f"multicast address {ip}"
    if ip.is_reserved:
        return f"reserved address {ip}"
    if ip.is_unspecified:
        return f"unspecified address {ip}"
    return None


def _resolve_hostname(
    hostname: str,
    *,
    resolver=None,
    timeout: float = DEFAULT_RESOLVE_TIMEOUT,
) -> tuple[str, ...]:
    """Resolve *hostname* to all A/AAAA records (injectable for tests).

    Any resolution failure raises SSRFBlockedError — fail-closed: if we cannot
    confirm an address is public, we do not fetch.
    """
    if resolver is not None:
        try:
            return tuple(resolver(hostname))
        except SSRFBlockedError:
            raise
        except Exception as exc:
            raise SSRFBlockedError(f"cannot resolve hostname {hostname!r}: {exc}") from exc
    try:
        infos = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"cannot resolve hostname {hostname!r}: {exc}") from exc
    except OSError as exc:
        raise SSRFBlockedError(f"DNS resolution failed for {hostname!r}: {exc}") from exc
    return tuple({info[4][0] for info in infos})


def check_url(
    url: str,
    *,
    resolver=None,
    resolve_timeout: float = DEFAULT_RESOLVE_TIMEOUT,
) -> SSRFDecision:
    """Validate *url* for outbound fetching; never performs the request itself."""
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        return SSRFDecision(False, f"unparseable URL: {exc}")

    if parsed.scheme.lower() not in _SCHEME_ALLOWLIST:
        return SSRFDecision(False, f"scheme {parsed.scheme!r} not allowed (http/https only)")

    hostname = parsed.hostname
    if not hostname:
        return SSRFDecision(False, "URL has no hostname")

    # Literal IPs are checked directly (getaddrinfo would also catch these,
    # but an explicit check gives precise reasons and works without DNS).
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        reason = _is_disallowed_ip(literal)
        if reason:
            return SSRFDecision(False, reason, (str(literal),))
        return SSRFDecision(True, "literal public IP", (str(literal),))

    try:
        resolved = _resolve_hostname(hostname, resolver=resolver, timeout=resolve_timeout)
    except SSRFBlockedError as exc:
        return SSRFDecision(False, str(exc))

    if not resolved:
        return SSRFDecision(False, f"hostname {hostname!r} resolved to no addresses")

    for ip_str in resolved:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return SSRFDecision(False, f"resolver returned malformed address {ip_str!r}")
        reason = _is_disallowed_ip(ip)
        if reason:
            return SSRFDecision(False, reason, resolved)

    return SSRFDecision(True, "all resolved addresses public", resolved)


def assert_safe_url(url: str, *, resolver=None) -> None:
    """Raise :class:`SSRFBlockedError` unless *url* passes the guard.

    No-op when the guard is disabled via ``ENRICH_SSRF_GUARD=0``.
    """
    if not ssrf_guard_enabled():
        return
    decision = check_url(url, resolver=resolver)
    if not decision.allowed:
        raise SSRFBlockedError(f"SSRF guard blocked {url!r}: {decision.reason}")


def is_safe_url(url: str, *, resolver=None) -> bool:
    """Boolean convenience wrapper around :func:`check_url` (guard-aware)."""
    if not ssrf_guard_enabled():
        return True
    return check_url(url, resolver=resolver).allowed
