#!/usr/bin/env python3
"""ora_parse_design.py — extract `========== FILE: <path> ==========` blocks
from ORA's design output and write each block to disk.

Usage: python ora_parse_design.py <ora_out.json>
"""
import json
import re
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.stderr.write("usage: ora_parse_design.py <ora_out.json>\n")
    sys.exit(2)

d = json.load(open(sys.argv[1]))
content = d.get("content") or ""

# Strict format: ========== FILE: /path/to/file ==========\n```lang?\n<body>\n```
pattern = re.compile(
    r"={5,}\s*FILE:\s*(\S+?)\s*={5,}\s*\n```\w*\n([\s\S]*?)\n```",
    re.MULTILINE,
)

created = []
for m in pattern.finditer(content):
    path = m.group(1).strip()
    body = m.group(2)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    created.append({"path": str(p), "bytes": len(body), "lines": body.count("\n") + 1})

print(json.dumps({"created": created, "count": len(created)}, indent=2))
