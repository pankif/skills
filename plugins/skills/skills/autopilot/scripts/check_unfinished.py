#!/usr/bin/env python3
"""Report unfinished sentinel occurrences without claiming completeness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator


DEFAULT_PATTERNS = (
    "TODO(autopilot:",
    "UNIMPL(autopilot:",
    "UNIMPL:autopilot:",
    "AUTOPILOT_UNFINISHED:",
)
SKIP_DIRS = {".git", ".skill-runs", "node_modules", "build", "dist", "vendor"}


def iter_files(paths: list[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for path in paths:
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path
            continue
        if not path.exists():
            continue
        for candidate in path.rglob("*"):
            relative_directory_parts = candidate.relative_to(path).parts[:-1]
            if not candidate.is_file() or any(
                part in SKIP_DIRS for part in relative_directory_parts
            ):
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate


def scan_markers(
    paths: list[Path], patterns: list[str]
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    findings: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    for path in iter_files(paths):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append({"path": str(path), "reason": str(exc)})
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for pattern in patterns:
                if pattern in line:
                    findings.append(
                        {
                            "path": str(path),
                            "line": line_number,
                            "pattern": pattern,
                        }
                    )
    return findings, skipped


def find_markers(paths: list[Path], patterns: list[str]) -> list[dict[str, object]]:
    """Compatibility helper for callers that only inspect findings."""
    findings, _ = scan_markers(paths, patterns)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="sentinel substring; repeat to replace the default set",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    missing = [str(path) for path in args.paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"missing path: {path}", file=sys.stderr)
        return 2

    patterns = args.patterns or list(DEFAULT_PATTERNS)
    findings, skipped = scan_markers(args.paths, patterns)
    if args.as_json:
        print(
            json.dumps(
                {"findings": findings, "skipped": skipped},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(f"{finding['path']}:{finding['line']}: {finding['pattern']}")
        print(f"unfinished sentinel occurrences: {len(findings)}")
        for item in skipped:
            print(f"incomplete scan: {item['path']}: {item['reason']}", file=sys.stderr)
    if skipped:
        return 3
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
