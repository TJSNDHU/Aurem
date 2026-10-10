"""007 Injection Scanner -- Specialized scanner for injection vulnerabilities.

Detects code injection, SQL injection, command injection, prompt injection,
XSS, SSRF, and path traversal patterns across Python, JavaScript/Node.js,
and shell codebases.  Performs context-aware analysis to reduce false positives
by tracking user-input sources and adjusting severity for hardcoded values,
test files, comments, and docstrings.

Usage:
    python injection_scanner