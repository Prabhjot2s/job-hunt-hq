"""Fetching URLs that came from outside (job links, company websites) safely.

Every hop of a redirect chain must be a public http(s) address: no localhost, private network,
link-local (cloud metadata) or reserved addresses, so a link can't make this tool talk to your
router, your other local apps or the dashboard. Residual risk: DNS can change between this check
and the actual connection (DNS rebinding); the dashboard's Host-header check still blocks that path.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

BLOCKED_HOSTS = ("linkedin.com", "indeed.", "ziprecruiter.", "glassdoor.")


def public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, ValueError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(infos)


def check_url(url: str, block_job_boards=True):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError(f"not a web address: {url}")
    if u.username or u.password:
        raise ValueError(f"addresses with a login part aren't fetched: {url}")
    if block_job_boards and any(b in u.hostname for b in BLOCKED_HOSTS):
        raise ValueError(f"{u.hostname} blocks scripts; find the employer's own posting instead")
    if not public_host(u.hostname):
        raise ValueError(f"not a public web address: {url}")


def safe_get(session, url, timeout=20, block_job_boards=True, **kw):
    """GET that re-checks every redirect hop."""
    for _ in range(6):
        check_url(url, block_job_boards)
        r = session.get(url, timeout=timeout, allow_redirects=False, **kw)
        if r.is_redirect and r.headers.get("Location"):
            url = urljoin(url, r.headers["Location"])
            continue
        return r
    raise ValueError("too many redirects")
