# -*- coding: utf-8 -*-
"""Shared security helpers for the vocabcard plugin."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


LOCAL_CDP_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _is_loopback_host(host: str) -> bool:
    if host in LOCAL_CDP_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_cdp_url(url: str, allow_remote: bool = False) -> str:
    """Validate a CDP endpoint URL.

    By default only loopback hosts are allowed. Remote hosts require an
    explicit allow_remote flag because CDP has no built-in auth.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        return ""

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        raise ValueError(
            f"CDP URL scheme must be http/https/ws/wss, got: {parsed.scheme or '(empty)'}"
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("CDP URL must include a hostname")

    if not allow_remote and not _is_loopback_host(host):
        raise ValueError(
            f"CDP host '{host}' is not loopback. "
            "Enable allow_remote_cdp only on trusted networks."
        )

    return cleaned
