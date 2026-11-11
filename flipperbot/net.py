"""HTTPS for the whole bot, stdlib only.

The Python that uv installs carries its own OpenSSL, which on some Macs can't
find the system's trusted certificates, so every HTTPS call fails with
CERTIFICATE_VERIFY_FAILED. macOS keeps them in /etc/ssl/cert.pem: load that too.
"""

from __future__ import annotations

import os
import ssl
import urllib.error
import urllib.request
from typing import Any

SYSTEM_CA_FILES = ["/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"]


def _context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    for path in SYSTEM_CA_FILES:
        if os.path.exists(path):
            try:
                ctx.load_verify_locations(path)
            except (ssl.SSLError, OSError):
                pass
            break
    return ctx


CONTEXT = _context()


def urlopen(req: Any, timeout: float = 30) -> Any:
    return urllib.request.urlopen(req, timeout=timeout, context=CONTEXT)


def explain(e: Exception) -> str:
    """A plain-words reason for a failed request."""
    if isinstance(e, urllib.error.HTTPError):
        return f"the server answered {e.code} {e.reason}"
    reason = getattr(e, "reason", e)
    if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper():
        return f"secure connection failed ({reason})"
    return f"couldn't connect ({reason}). Is the Mac online?"
