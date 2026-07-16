#!/usr/bin/env python3
"""Validate only the structural syntax contract of a spec skill output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path


REQUIRED_FRONTMATTER = ("title", "domain", "last_updated")
REQUIRED_H2 = (
    "Purpose",
    "Glossary",
    "Actors",
    "User-facing behavior",
    "Flows",
    "States and transitions",
    "Invariants",
    "Edge cases",
    "Success criteria",
    "Out of scope",
    "Open questions",
    "Technical appendix",
)
REQUIRED_APPENDIX_H3 = (
    "Evidence and conflicts",
    "Stack & placement",
    "Data model and contracts",
    "Migration & rollback",
    "Integration points",
    "Risks & follow-ups",
)

# Deliberately support a small deterministic scalar subset rather than claiming
# to implement YAML: single-quoted strings (with doubled quote escapes), JSON-style
# double-quoted strings, and plain ASCII words/numbers with spaces, dots, slashes,
# underscores, or hyphens. Values containing other syntax must be quoted.
SUPPORTED_SCALAR = re.compile(
    r'''(?:'(?:[^']|'')*'|"(?:[^"\\]|\\.)*"|[A-Za-z0-9][A-Za-z0-9 _./-]*)'''
)


def _decode_scalar(raw: str) -> str:
    if raw.startswith("'"):
        return raw[1:-1].replace("''", "'")
    if raw.startswith('"'):
        return json.loads(raw)
    return raw


def _frontmatter(lines: list[str], errors: list[str]) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        errors.append("line 1: expected opening YAML frontmatter delimiter '---'")
        return {}, 0

    try:
        closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        errors.append("frontmatter: missing closing delimiter '---'")
        return {}, 0

    values: dict[str, str] = {}
    for index, line in enumerate(lines[1:closing], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*", line)
        if not match:
            errors.append(f"line {index}: unsupported frontmatter entry")
            continue

        key, raw = match.groups()
        if key not in REQUIRED_FRONTMATTER:
            errors.append(f"line {index}: unsupported frontmatter key '{key}'")
            continue
        if key in values:
            errors.append(f"line {index}: duplicate frontmatter key '{key}'")
            continue
        if not raw or not SUPPORTED_SCALAR.fullmatch(raw):
            errors.append(f"line {index}: unsupported frontmatter scalar for '{key}'")
            continue
        try:
            values[key] = _decode_scalar(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            errors.append(f"line {index}: invalid quoted scalar for '{key}'")

    for key in REQUIRED_FRONTMATTER:
        if not values.get(key):
            errors.append(f"frontmatter: missing non-empty '{key}'")

    raw_date = values.get("last_updated", "")
    if raw_date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
            errors.append("frontmatter: 'last_updated' must use YYYY-MM-DD")
        else:
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                errors.append("frontmatter: 'last_updated' must be a real calendar date")

    return values, closing


def _validate_required_headings(
    names: list[str], required: tuple[str, ...], prefix: str, errors: list[str]
) -> None:
    for heading in required:
        count = names.count(heading)
        if count != 1:
            errors.append(
                f"headings: expected exactly one '{prefix} {heading}', found {count}"
            )

    unexpected = [name for name in names if name not in required]
    if unexpected:
        errors.append(
            f"headings: unexpected {prefix} section(s): " + ", ".join(unexpected)
        )

    if all(names.count(name) == 1 for name in required):
        actual = [name for name in names if name in required]
        if actual != list(required):
            errors.append(f"headings: required {prefix} sections are out of order")


def validate_text(text: str) -> list[str]:
    """Return structural syntax errors; empty means syntax-valid, not semantically valid."""

    lines = text.splitlines()
    errors: list[str] = []
    frontmatter, frontmatter_end = _frontmatter(lines, errors)

    body = lines[frontmatter_end + 1 :]
    h1_entries = [
        (line[2:].strip(), frontmatter_end + offset + 2)
        for offset, line in enumerate(body)
        if line.startswith("# ")
    ]
    if len(h1_entries) != 1:
        errors.append(f"body: expected exactly one H1 title, found {len(h1_entries)}")
    elif frontmatter.get("title") and h1_entries[0][0] != frontmatter["title"]:
        errors.append("body: H1 title must exactly match frontmatter 'title'")

    h2_entries = [
        (line[3:].strip(), frontmatter_end + offset + 2)
        for offset, line in enumerate(body)
        if line.startswith("## ")
    ]
    h2_names = [name for name, _ in h2_entries]
    _validate_required_headings(h2_names, REQUIRED_H2, "##", errors)

    appendix_matches = [line for name, line in h2_entries if name == "Technical appendix"]
    if len(appendix_matches) == 1:
        appendix_line = appendix_matches[0]
        prior_nonblank = next(
            (lines[i].strip() for i in range(appendix_line - 2, -1, -1) if lines[i].strip()),
            "",
        )
        if prior_nonblank != "---":
            errors.append("boundary: '## Technical appendix' must be preceded by a horizontal rule")

        first_after_appendix = next(
            (lines[i].lstrip() for i in range(appendix_line, len(lines)) if lines[i].strip()),
            "",
        )
        if not first_after_appendix.startswith(">"):
            errors.append("boundary: technical appendix must begin with a blockquote warning")

        appendix_h3 = [
            line[4:].strip()
            for line in lines[appendix_line:]
            if line.startswith("### ")
        ]
        _validate_required_headings(
            appendix_h3, REQUIRED_APPENDIX_H3, "###", errors
        )

    return errors


def validate_file(path: Path) -> list[str]:
    try:
        return validate_text(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"file: {exc}"]
    except UnicodeError as exc:
        return [f"file: expected UTF-8 text ({exc})"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate SPEC.md structural syntax only; semantics and evidence are out of scope."
    )
    parser.add_argument("spec", type=Path, help="Path to SPEC.md")
    args = parser.parse_args(argv)

    errors = validate_file(args.spec)
    if errors:
        print(f"syntax-invalid: {args.spec}", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"syntax-validated: {args.spec}")
    print("note: structure only; semantic correctness and evidence were not validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
