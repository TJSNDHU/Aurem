"""
Shannon Runner — In-Process Real Pentest
=========================================
Performs REAL security probes against a target URL (no Legion required).
Pushes the resulting report straight into `shannon_security.ingest_report()`
so the existing dashboards light up with actionable findings.

Non-destructive probes only: HEAD/GET, no fuzzing, no POST, no exploitation.

Check categories:
  1. TLS / certificate hygiene (expiry, protocol)
  2. HTTP security headers (HSTS, CSP, X-Frame-Options, etc.)
  3. Cookie flags (Secure, HttpOnly, SameSite)
  4. CORS wildcard / credential leak
  5. Server banner / version disclosure
  6. Sensitive path exposure (.env, .git, backup files, swagger)
  7. HTTP → HTTPS redirect enforcement
"""
from __future__ import annotations

import asyncio
import logging
import socket
import ssl
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


async def _check_tls(hostname: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        ctx = ssl.create_default_context()
        loop = asyncio.get_event_loop()

        def _grab():
            with socket.create_connection((hostname, 443), timeout=6) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    return ssock.version(), ssock.getpeercert()

        version, cert = await loop.run_in_executor(None, _grab)
        not_after = cert.get("notAfter", "")
        try:
            expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days_left = (expiry - datetime.now(timezone.utc)).days
            if days_left < 0:
                findings.append({
                    "severity": "critical", "title": "TLS certificate EXPIRED",
                    "category": "tls", "cwe": "CWE-295",
                    "description": f"Certificate for {hostname} expired {-days_left} days ago.",
                    "fix_suggestion": "Renew the certificate immediately (Let's Encrypt / ACM auto-renew).",
                    "verified": True,
                })
            elif days_left < 14:
                findings.append({
                    "severity": "high", "title": "TLS certificate expires soon",
                    "category": "tls", "cwe": "CWE-295",
                    "description": f"Certificate for {hostname} expires in {days_left} days.",
                    "fix_suggestion": "Enable auto-renew or renew manually before expiry.",
                    "verified": True,
                })
        except Exception:
            pass

        if version and version in ("TLSv1", "TLSv1.1"):
            findings.append({
                "severity": "high", "title": f"Weak TLS protocol negotiated: {version}",
                "category": "tls", "cwe": "CWE-326",
                "description": "Modern browsers consider TLS 1.0/1.1 insecure.",
                "fix_suggestion": "Disable TLS 1.0/1.1 on the load-balancer; enforce TLS 1.2+.",
                "verified": True,
            })
    except Exception as e:
        findings.append({
            "severity": "medium", "title": "TLS handshake check failed",
            "category": "tls",
            "description": f"Could not complete TLS handshake to {hostname}: {e}",
            "fix_suggestion": "Verify port 443 is reachable and TLS is terminating correctly.",
            "verified": False,
        })
    return findings


async def _check_security_headers(client: httpx.AsyncClient, url: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        r = await client.get(url, follow_redirects=True, timeout=8.0)
        headers_lower = {k.lower(): v for k, v in r.headers.items()}

        required = {
            "strict-transport-security": ("high", "HSTS header missing",
                "Add `Strict-Transport-Security: max-age=31536000; includeSubDomains`.", "CWE-319"),
            "x-content-type-options": ("medium", "X-Content-Type-Options missing",
                "Add `X-Content-Type-Options: nosniff` to prevent MIME-sniffing.", "CWE-693"),
            "x-frame-options": ("medium", "X-Frame-Options / frame-ancestors missing",
                "Set `X-Frame-Options: DENY` or CSP `frame-ancestors 'none'`.", "CWE-1021"),
            "referrer-policy": ("low", "Referrer-Policy missing",
                "Add `Referrer-Policy: strict-origin-when-cross-origin`.", "CWE-200"),
            "content-security-policy": ("medium", "Content-Security-Policy missing",
                "Ship a CSP — start with `default-src 'self'` and iterate.", "CWE-79"),
            "permissions-policy": ("low", "Permissions-Policy missing",
                "Add `Permissions-Policy: geolocation=(), camera=(), microphone=()`.", "CWE-693"),
        }
        for h, (sev, title, fix, cwe) in required.items():
            if h not in headers_lower:
                findings.append({
                    "severity": sev, "title": title, "category": "headers",
                    "cwe": cwe, "description": f"Response to {url} has no `{h}` header.",
                    "fix_suggestion": fix, "verified": True,
                })

        server_val = headers_lower.get("server", "")
        if server_val and any(tok in server_val.lower() for tok in ("apache/", "nginx/", "iis/", "openresty/")):
            findings.append({
                "severity": "low", "title": f"Server banner discloses version: {server_val}",
                "category": "disclosure", "cwe": "CWE-200",
                "description": "Exact server version aids attackers mapping CVEs.",
                "fix_suggestion": "Strip or anonymize the `Server` header at the reverse proxy.",
                "verified": True,
            })

        if "x-powered-by" in headers_lower:
            findings.append({
                "severity": "low", "title": f"X-Powered-By discloses stack: {headers_lower['x-powered-by']}",
                "category": "disclosure", "cwe": "CWE-200",
                "description": "Tech-stack fingerprinting exposed.",
                "fix_suggestion": "Remove `X-Powered-By` at the framework or proxy layer.",
                "verified": True,
            })

        # Cookie flag audit
        set_cookies = []
        if hasattr(r.headers, "get_list"):
            set_cookies = r.headers.get_list("set-cookie")
        elif "set-cookie" in r.headers:
            set_cookies = [r.headers["set-cookie"]]
        for cookie in set_cookies:
            c_lower = cookie.lower()
            name = cookie.split("=", 1)[0].strip()
            if "secure" not in c_lower:
                findings.append({
                    "severity": "medium", "title": f"Cookie `{name}` missing Secure flag",
                    "category": "cookies", "cwe": "CWE-614",
                    "description": "Cookies sent over HTTP can be intercepted.",
                    "fix_suggestion": "Set `Secure` attribute on all cookies.", "verified": True,
                })
            if "httponly" not in c_lower:
                findings.append({
                    "severity": "medium", "title": f"Cookie `{name}` missing HttpOnly flag",
                    "category": "cookies", "cwe": "CWE-1004",
                    "description": "Cookie readable from JS → XSS can steal it.",
                    "fix_suggestion": "Set `HttpOnly` on session/auth cookies.", "verified": True,
                })
            if "samesite" not in c_lower:
                findings.append({
                    "severity": "low", "title": f"Cookie `{name}` missing SameSite attribute",
                    "category": "cookies", "cwe": "CWE-352",
                    "description": "Cookie may be sent cross-site → CSRF risk.",
                    "fix_suggestion": "Set `SameSite=Lax` (or `Strict` for auth cookies).", "verified": True,
                })
    except Exception as e:
        findings.append({
            "severity": "medium", "title": "Security header check failed",
            "category": "headers",
            "description": f"Could not probe {url}: {e}",
            "fix_suggestion": "Verify target is reachable.", "verified": False,
        })
    return findings


async def _check_cors(client: httpx.AsyncClient, url: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        r = await client.get(url, headers={"Origin": "https://evil.example"},
                              timeout=8.0, follow_redirects=True)
        aco = r.headers.get("access-control-allow-origin", "")
        acc = r.headers.get("access-control-allow-credentials", "").lower()
        if aco == "*" and acc == "true":
            findings.append({
                "severity": "critical", "title": "CORS misconfig — wildcard + credentials",
                "category": "cors", "cwe": "CWE-942",
                "description": "Any origin can read authenticated responses.",
                "fix_suggestion": "Remove `Access-Control-Allow-Credentials` OR restrict origin.",
                "verified": True,
            })
        elif aco == "https://evil.example":
            findings.append({
                "severity": "high", "title": "CORS reflects arbitrary origin",
                "category": "cors", "cwe": "CWE-942",
                "description": "Server reflects any `Origin` into `Access-Control-Allow-Origin`.",
                "fix_suggestion": "Maintain an allow-list of trusted origins.", "verified": True,
            })
    except Exception:
        pass
    return findings


async def _check_sensitive_paths(client: httpx.AsyncClient, base: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    paths = [
        ("/.env", "critical", "CWE-200", "Environment file publicly readable"),
        ("/.git/config", "critical", "CWE-200", ".git directory exposed"),
        ("/.git/HEAD", "critical", "CWE-200", ".git HEAD exposed"),
        ("/backup.sql", "high", "CWE-200", "SQL backup publicly exposed"),
        ("/backup.zip", "high", "CWE-200", "Backup archive publicly exposed"),
        ("/phpinfo.php", "high", "CWE-200", "phpinfo() page reachable"),
        ("/server-status", "high", "CWE-200", "Apache server-status reachable"),
        ("/.DS_Store", "low", "CWE-200", ".DS_Store file exposed"),
        ("/api/docs", "info", None, "Swagger docs publicly reachable"),
        ("/redoc", "info", None, "ReDoc publicly reachable"),
    ]

    # SPA false-positive guard: sample a guaranteed-404 path. If the server
    # returns a 200 with HTML (SPA catch-all like React Router), we know
    # every other "sensitive path" will also appear 200 with the same HTML,
    # so we should NOT flag them. We detect this by recording the SPA body
    # fingerprint and skipping matches.
    spa_fingerprint = None
    try:
        probe = await client.get(
            base.rstrip("/") + "/___definitely_not_a_real_path_xyz_42",
            timeout=5.0, follow_redirects=False,
        )
        if 200 <= probe.status_code < 300 and "text/html" in probe.headers.get("content-type", "").lower():
            # SPA catch-all detected. Fingerprint = first 300 bytes of body.
            spa_fingerprint = probe.content[:300]
    except Exception:
        pass

    for path, sev, cwe, desc in paths:
        url = base.rstrip("/") + path
        try:
            r = await client.get(url, timeout=5.0, follow_redirects=False)
            if not (200 <= r.status_code < 300) or len(r.content) <= 10:
                continue

            ctype = r.headers.get("content-type", "").lower()

            # Guard 1: SPA catch-all — same body as our probe
            if spa_fingerprint and r.content[:300] == spa_fingerprint:
                continue

            # Guard 2: HTML response for a non-HTML asset is almost always SPA
            if "text/html" in ctype and path not in ("/api/docs", "/redoc"):
                continue

            f = {
                "severity": sev, "title": f"Sensitive path reachable: {path}",
                "category": "exposure",
                "description": f"{desc} — HTTP {r.status_code}, {len(r.content)} bytes, content-type: {ctype}",
                "fix_suggestion": f"Return 404/403 for {path} at the reverse-proxy or app layer.",
                "verified": True,
            }
            if cwe:
                f["cwe"] = cwe
            findings.append(f)
        except Exception:
            pass
    return findings


async def _check_https_redirect(client: httpx.AsyncClient, hostname: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        r = await client.get(f"http://{hostname}/", timeout=6.0, follow_redirects=False)
        if r.status_code < 300 or r.status_code >= 400:
            findings.append({
                "severity": "high", "title": "HTTP → HTTPS redirect missing",
                "category": "tls", "cwe": "CWE-319",
                "description": f"http://{hostname}/ returned HTTP {r.status_code} instead of 301/302 to HTTPS.",
                "fix_suggestion": "Force 301 from port 80 to https:// at the load balancer / proxy.",
                "verified": True,
            })
        else:
            loc = r.headers.get("location", "")
            if not loc.lower().startswith("https://"):
                findings.append({
                    "severity": "high", "title": "HTTP redirects to non-HTTPS target",
                    "category": "tls", "cwe": "CWE-319",
                    "description": f"Redirect location is `{loc}`, not https://",
                    "fix_suggestion": "Ensure redirect target starts with https://.", "verified": True,
                })
    except Exception:
        pass  # port 80 closed is good, no finding
    return findings


async def run_real_audit(target_url: str) -> Dict[str, Any]:
    """Execute all checks against target_url and feed into the Shannon ingest pipeline."""
    start = datetime.now(timezone.utc)
    parsed = urlparse(target_url if "://" in target_url else f"https://{target_url}")
    hostname = parsed.hostname or parsed.netloc
    base = f"{parsed.scheme or 'https'}://{hostname}"

    async with httpx.AsyncClient(
        verify=True,
        headers={"User-Agent": "ShannonRunner/1.0 (AUREM Security Audit)"},
    ) as client:
        results = await asyncio.gather(
            _check_tls(hostname),
            _check_security_headers(client, base),
            _check_cors(client, base),
            _check_sensitive_paths(client, base),
            _check_https_redirect(client, hostname),
            return_exceptions=True,
        )

    vulns: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            vulns.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"[ShannonRunner] check raised: {r}")

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    report = {
        "target": base,
        "url": base,
        "timestamp": start.isoformat(),
        "duration_seconds": round(duration, 2),
        "scanner": "shannon_runner_v1",
        "version": "1.0",
        "vulnerabilities": vulns,
    }

    from services.shannon_security import ingest_report
    processed = await ingest_report(report)
    logger.info(
        f"[ShannonRunner] {base} → score {processed['security_score']}/100, "
        f"{processed['total_vulnerabilities']} findings "
        f"({processed['severity_counts']['critical']}C/{processed['severity_counts']['high']}H) "
        f"in {duration:.1f}s"
    )
    return processed


async def shannon_runner_scheduler():
    """Weekly scheduler — runs an audit every 7 days against aurem.live."""
    import os
    await asyncio.sleep(180)  # 3 min startup grace
    target = os.environ.get("SHANNON_AUDIT_TARGET", "https://aurem.live")
    interval_hours = int(os.environ.get("SHANNON_AUDIT_INTERVAL_HOURS", "168"))  # 7 days
    while True:
        try:
            logger.info(f"[ShannonRunner] Weekly audit starting for {target}")
            result = await run_real_audit(target)
            logger.info(
                f"[ShannonRunner] Weekly audit done: score={result.get('security_score')} "
                f"vulns={result.get('total_vulnerabilities')}"
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[ShannonRunner] scheduler error: {e}")
        await asyncio.sleep(interval_hours * 3600)
