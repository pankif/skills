#!/usr/bin/env python3
"""Validate or seal an Autopilot BUS v2 record with the Python stdlib.

The validator checks supported syntax, vocabulary, references, prompt identity
when supplied, and canonical integrity. It cannot validate semantic truth, risk
judgment, behavioral correctness, or user authority.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2
ANALYSIS_VERSION = "autopilot-0.6"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MODES = {"plan", "build", "ship"}
CATEGORIES = {
    "public-contract",
    "persistent-format",
    "destructive",
    "trust-boundary",
    "outward-effect",
    "real-world-mutation",
    "internal",
}
REACH = {"local", "external", "unknown"}
DISPOSITIONS = {"derived", "defaulted", "open", "stop"}
PROVENANCE = {
    "explicit-user",
    "code",
    "configuration",
    "test",
    "standard",
    "inference",
    "unknown",
}
OUTWARD_ACTIONS = {"commit", "branch", "push", "pull-request"}
ZERO_DIGEST = "0" * 64
ROOT_KEYS = {
    "schema_version",
    "analysis_version",
    "run_id",
    "mode",
    "depth",
    "target",
    "prompt_sha256",
    "decisions",
    "unfinished_markers",
    "disclosure_decision_ids",
    "outward_authority",
    "integrity",
}
DECISION_KEYS = {
    "id",
    "category",
    "reach",
    "disposition",
    "statement",
    "blast_rank",
    "provenance",
}
PROVENANCE_KEYS = {"kind", "reference"}
AUTHORITY_KEYS = {"action", "target", "current_request_evidence"}
INTEGRITY_KEYS = {"algorithm", "canonical_sha256"}


def normalize_prompt(text: str) -> str:
    normalized_newlines = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", normalized_newlines)


def prompt_digest(text: str) -> str:
    return hashlib.sha256(normalize_prompt(text).encode("utf-8")).hexdigest()


def canonical_digest(record: dict[str, Any]) -> str:
    normalized = copy.deepcopy(record)
    integrity = normalized.setdefault("integrity", {})
    integrity["algorithm"] = "sha256"
    integrity["canonical_sha256"] = ZERO_DIGEST
    payload = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_keys(
    value: dict[str, Any], expected: set[str], field: str, errors: list[str]
) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        errors.append(f"{field} missing required fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{field} has unknown fields: {', '.join(unknown)}")


def _string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not _nonempty_string(item):
            errors.append(f"{field}[{index}] must be a non-empty string")
        else:
            result.append(item)
    if len(result) != len(set(result)):
        errors.append(f"{field} must not contain duplicates")
    return result


def _enum(value: Any, allowed: Iterable[str], field: str, errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{field} has unsupported value {value!r}")


def validate_record(
    record: Any,
    *,
    check_digest: bool = True,
    prompt_text: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["root must be a JSON object"]

    version = record.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        return [
            f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}; "
            "preserve the artifact and migrate or restart"
        ]
    if record.get("analysis_version") != ANALYSIS_VERSION:
        return [
            f"unsupported analysis_version {record.get('analysis_version')!r}; "
            f"expected {ANALYSIS_VERSION!r}; preserve the artifact"
        ]

    _check_keys(record, ROOT_KEYS, "root", errors)
    for field in ("run_id", "target"):
        if not _nonempty_string(record.get(field)):
            errors.append(f"{field} must be a non-empty string")
    _enum(record.get("mode"), MODES, "mode", errors)
    if record.get("depth") != "strict":
        errors.append("depth must be 'strict' for a BUS record")

    stored_prompt_hash = record.get("prompt_sha256")
    if not isinstance(stored_prompt_hash, str) or not HEX64.fullmatch(stored_prompt_hash):
        errors.append("prompt_sha256 must be 64 lowercase hexadecimal characters")
    elif prompt_text is not None and stored_prompt_hash != prompt_digest(prompt_text):
        errors.append("prompt_sha256 does not match the supplied normalized prompt")

    decisions = record.get("decisions")
    decision_ids: list[str] = []
    if not isinstance(decisions, list):
        errors.append("decisions must be an array")
    else:
        for index, decision in enumerate(decisions):
            prefix = f"decisions[{index}]"
            if not isinstance(decision, dict):
                errors.append(f"{prefix} must be an object")
                continue
            _check_keys(decision, DECISION_KEYS, prefix, errors)
            decision_id = decision.get("id")
            if not _nonempty_string(decision_id):
                errors.append(f"{prefix}.id must be a non-empty string")
            else:
                decision_ids.append(decision_id)
            _enum(decision.get("category"), CATEGORIES, f"{prefix}.category", errors)
            _enum(decision.get("reach"), REACH, f"{prefix}.reach", errors)
            _enum(
                decision.get("disposition"),
                DISPOSITIONS,
                f"{prefix}.disposition",
                errors,
            )
            if not _nonempty_string(decision.get("statement")):
                errors.append(f"{prefix}.statement must be a non-empty string")
            blast_rank = decision.get("blast_rank")
            if (
                not isinstance(blast_rank, int)
                or isinstance(blast_rank, bool)
                or not 0 <= blast_rank <= 100
            ):
                errors.append(f"{prefix}.blast_rank must be an integer from 0 to 100")
            provenance = decision.get("provenance")
            if not isinstance(provenance, dict):
                errors.append(f"{prefix}.provenance must be an object")
            else:
                _check_keys(provenance, PROVENANCE_KEYS, f"{prefix}.provenance", errors)
                _enum(
                    provenance.get("kind"),
                    PROVENANCE,
                    f"{prefix}.provenance.kind",
                    errors,
                )
                if not _nonempty_string(provenance.get("reference")):
                    errors.append(
                        f"{prefix}.provenance.reference must be a non-empty string"
                    )
        if len(decision_ids) != len(set(decision_ids)):
            errors.append("decision IDs must be unique")

    _string_list(record.get("unfinished_markers"), "unfinished_markers", errors)
    disclosure_ids = _string_list(
        record.get("disclosure_decision_ids"),
        "disclosure_decision_ids",
        errors,
    )
    unknown_ids = sorted(set(disclosure_ids) - set(decision_ids))
    if unknown_ids:
        errors.append(
            "disclosure_decision_ids reference unknown decisions: "
            + ", ".join(unknown_ids)
        )

    authority = record.get("outward_authority")
    authority_pairs: list[tuple[str, str]] = []
    if not isinstance(authority, list):
        errors.append("outward_authority must be an array")
    else:
        for index, receipt in enumerate(authority):
            prefix = f"outward_authority[{index}]"
            if not isinstance(receipt, dict):
                errors.append(f"{prefix} must be an object")
                continue
            _check_keys(receipt, AUTHORITY_KEYS, prefix, errors)
            action = receipt.get("action")
            target = receipt.get("target")
            _enum(action, OUTWARD_ACTIONS, f"{prefix}.action", errors)
            if not _nonempty_string(target):
                errors.append(f"{prefix}.target must be a non-empty string")
            if not _nonempty_string(receipt.get("current_request_evidence")):
                errors.append(
                    f"{prefix}.current_request_evidence must be a non-empty string"
                )
            if isinstance(action, str) and isinstance(target, str):
                authority_pairs.append((action, target))
        if len(authority_pairs) != len(set(authority_pairs)):
            errors.append("outward_authority must not duplicate action-target pairs")

    integrity = record.get("integrity")
    if not isinstance(integrity, dict):
        errors.append("integrity must be an object")
    else:
        _check_keys(integrity, INTEGRITY_KEYS, "integrity", errors)
        if integrity.get("algorithm") != "sha256":
            errors.append("integrity.algorithm must be 'sha256'")
        digest = integrity.get("canonical_sha256")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            errors.append(
                "integrity.canonical_sha256 must be 64 lowercase hexadecimal characters"
            )
        elif check_digest:
            expected = canonical_digest(record)
            if digest != expected:
                errors.append(
                    "integrity.canonical_sha256 does not match canonical record content"
                )

    return errors


def load_record(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="BUS.json path")
    parser.add_argument(
        "--seal",
        action="store_true",
        help="write the canonical digest after structural validation",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="optional original prompt whose normalized SHA-256 must match",
    )
    args = parser.parse_args(argv)

    try:
        record = load_record(args.path)
        prompt_text = (
            args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else None
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"BUS invalid: {exc}", file=sys.stderr)
        return 2

    if args.seal:
        if not isinstance(record, dict):
            print("BUS invalid: root must be a JSON object", file=sys.stderr)
            return 1
        record.setdefault("integrity", {})
        record["integrity"]["algorithm"] = "sha256"
        record["integrity"]["canonical_sha256"] = ZERO_DIGEST
        errors = validate_record(
            record, check_digest=False, prompt_text=prompt_text
        )
        if errors:
            for error in errors:
                print(f"BUS invalid: {error}", file=sys.stderr)
            return 1
        record["integrity"]["canonical_sha256"] = canonical_digest(record)
        args.path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        record = load_record(args.path)

    errors = validate_record(record, prompt_text=prompt_text)
    if errors:
        for error in errors:
            print(f"BUS invalid: {error}", file=sys.stderr)
        return 1
    print(f"BUS valid: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
