#!/usr/bin/env python3
"""Validate the structural compatibility of a diagnose CASE JSONL ledger.

This validator deliberately has a narrow scope. It checks supported version and
record structure; it does not verify evidence, command execution, causal claims,
or historical append-only behavior unless a previous snapshot is supplied.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "diagnose.case"
SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_ANALYSIS_VERSION = 1
HEADER_FIELDS = {
    "schema",
    "schema_version",
    "analysis_version",
    "record_type",
    "case_id",
    "created_at",
    "metadata",
}
EVENT_FIELDS = {
    "schema",
    "schema_version",
    "record_type",
    "case_id",
    "sequence",
    "timestamp",
    "payload",
}
EVENT_TYPES = {
    "oracle",
    "capability",
    "reproduction",
    "hypothesis",
    "probe",
    "control",
    "falsification",
    "terminal",
}
RFC3339_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class CaseValidationError(ValueError):
    """A CASE file is structurally invalid or incompatible."""


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CaseValidationError(f"cannot read {path}: {exc}") from exc


def _parse_timestamp(value: Any, field: str, line_number: int) -> None:
    if not isinstance(value, str) or RFC3339_TIMESTAMP.fullmatch(value) is None:
        raise CaseValidationError(
            f"line {line_number}: {field} must be an RFC3339 date-time with an explicit timezone"
        )
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CaseValidationError(
            f"line {line_number}: {field} must be an RFC3339 date-time with an explicit timezone"
        ) from exc
    if parsed.utcoffset() is None:
        raise CaseValidationError(
            f"line {line_number}: {field} must be an RFC3339 date-time with an explicit timezone"
        )


def _decode_records(path: Path, data: bytes) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaseValidationError(f"{path}: file is not UTF-8") from exc

    lines = text.splitlines()
    if not lines:
        raise CaseValidationError(f"{path}: CASE ledger is empty")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise CaseValidationError(f"line {line_number}: blank JSONL records are not allowed")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaseValidationError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise CaseValidationError(f"line {line_number}: record must be a JSON object")
        records.append(record)
    return records


def _require_common(record: dict[str, Any], line_number: int) -> None:
    if "schema_version" not in record:
        raise CaseValidationError(
            f"line {line_number}: unversioned/legacy CASE record is unsupported; preserve it and migrate explicitly"
        )
    if (
        type(record["schema_version"]) is not int
        or record["schema_version"] != SUPPORTED_SCHEMA_VERSION
    ):
        raise CaseValidationError(
            f"line {line_number}: unsupported schema_version {record['schema_version']!r}; "
            f"supported: {SUPPORTED_SCHEMA_VERSION}"
        )
    if record.get("schema") != SCHEMA:
        raise CaseValidationError(f"line {line_number}: schema must be {SCHEMA!r}")
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise CaseValidationError(f"line {line_number}: case_id must be a non-empty string")


def validate_case(path: Path) -> tuple[str, int]:
    data = _read_bytes(path)
    records = _decode_records(path, data)

    header = records[0]
    _require_common(header, 1)
    unknown = set(header) - HEADER_FIELDS
    if unknown:
        raise CaseValidationError(f"line 1: unknown header fields: {sorted(unknown)}")
    required_header = HEADER_FIELDS - {"metadata"}
    missing = required_header - set(header)
    if missing:
        raise CaseValidationError(f"line 1: missing header fields: {sorted(missing)}")
    if (
        type(header["analysis_version"]) is not int
        or header["analysis_version"] != SUPPORTED_ANALYSIS_VERSION
    ):
        raise CaseValidationError(
            f"line 1: unsupported analysis_version {header['analysis_version']!r}; "
            f"supported: {SUPPORTED_ANALYSIS_VERSION}"
        )
    if header.get("record_type") != "case_header":
        raise CaseValidationError("line 1: first record_type must be 'case_header'")
    _parse_timestamp(header.get("created_at"), "created_at", 1)
    if "metadata" in header and not isinstance(header["metadata"], dict):
        raise CaseValidationError("line 1: metadata must be an object")

    case_id = header["case_id"]
    expected_sequence = 1
    for line_number, record in enumerate(records[1:], start=2):
        _require_common(record, line_number)
        unknown = set(record) - EVENT_FIELDS
        if unknown:
            raise CaseValidationError(f"line {line_number}: unknown event fields: {sorted(unknown)}")
        missing = EVENT_FIELDS - set(record)
        if missing:
            raise CaseValidationError(f"line {line_number}: missing event fields: {sorted(missing)}")
        if record["record_type"] not in EVENT_TYPES:
            raise CaseValidationError(
                f"line {line_number}: unsupported record_type {record['record_type']!r}"
            )
        if record["case_id"] != case_id:
            raise CaseValidationError(f"line {line_number}: case_id does not match header")
        if type(record["sequence"]) is not int or record["sequence"] != expected_sequence:
            raise CaseValidationError(
                f"line {line_number}: sequence must be contiguous; expected {expected_sequence}"
            )
        _parse_timestamp(record["timestamp"], "timestamp", line_number)
        if not isinstance(record["payload"], dict):
            raise CaseValidationError(f"line {line_number}: payload must be an object")
        expected_sequence += 1

    return case_id, len(records) - 1


def validate_append(candidate: Path, previous: Path) -> None:
    validate_case(previous)
    previous_data = _read_bytes(previous)
    candidate_data = _read_bytes(candidate)
    if not candidate_data.startswith(previous_data):
        raise CaseValidationError(
            "candidate is not an append-only extension of the previous snapshot; existing bytes changed"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a diagnose CASE schema v1 / analysis v1 JSONL ledger"
    )
    parser.add_argument("case", type=Path, help="candidate CASE.jsonl path")
    parser.add_argument(
        "--previous",
        type=Path,
        help="optional previous snapshot; candidate must preserve it byte-for-byte as a prefix",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.previous is not None:
            validate_append(args.case, args.previous)
        case_id, event_count = validate_case(args.case)
    except CaseValidationError as exc:
        print(f"INVALID CASE: {exc}", file=sys.stderr)
        return 1

    append_note = " (append-safe against previous snapshot)" if args.previous else ""
    print(
        f"VALID CASE schema v{SUPPORTED_SCHEMA_VERSION} / analysis v{SUPPORTED_ANALYSIS_VERSION}: "
        f"{case_id}, {event_count} event(s){append_note}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
