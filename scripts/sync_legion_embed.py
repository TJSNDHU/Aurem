#!/usr/bin/env python3
"""Regenerate /app/backend/legion_embedded_assets.py base64 constants
from the canonical daemon + installer files. Run any time after editing
/app/aurem-cto/daemon/{legion_daemon.py, install.sh}."""
from __future__ import annotations
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "DAEMON_B64":  ROOT / "aurem-cto/daemon/legion_daemon.py",
    "INSTALL_B64": ROOT / "aurem-cto/daemon/install.sh",
}
TARGET = ROOT / "backend/legion_embedded_assets.py"

def main() -> int:
    text = TARGET.read_text()
    for var, src in SOURCES.items():
        b64 = base64.b64encode(src.read_bytes()).decode("ascii")
        # Replace existing constant assignment of any value
        import re
        pattern = re.compile(rf'^{var}\s*=\s*"[^"]*"$', re.M)
        replacement = f'{var} = "{b64}"'
        if pattern.search(text):
            text = pattern.sub(replacement, text)
        else:
            # First-time injection — replace the placeholder
            text = text.replace(f'"__{var}_PLACEHOLDER__"', f'"{b64}"')
        print(f"{var}: {len(b64)} chars from {src.name} ({src.stat().st_size} bytes)")
    TARGET.write_text(text)
    print(f"Updated {TARGET}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
