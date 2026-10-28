"""Check that relative links in Markdown files point at files that exist. Exits 1 and lists the broken links otherwise."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def tracked_markdown() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if line]


def broken_links(files: list[Path]) -> list[tuple[Path, str]]:
    bad = []
    for f in files:
        for target in LINK.findall(f.read_text(encoding="utf-8", errors="replace")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = target.split("#", 1)[0]
            if path and not (f.parent / path).exists():
                bad.append((f.relative_to(ROOT), target))
    return bad


if __name__ == "__main__":
    bad = broken_links(tracked_markdown())
    for f, t in bad:
        print(f"{f}: {t}")
    print(f"{len(bad)} broken link(s)")
    sys.exit(1 if bad else 0)
