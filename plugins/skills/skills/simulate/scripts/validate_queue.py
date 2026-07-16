#!/usr/bin/env python3
"""Validate simulate queue artifacts without third-party dependencies.

This checker proves a narrow set of mechanical properties: supported artifact
version, JSON shape, deterministic ordering, id/slug uniqueness, mode budgets,
bound declared-ID references, counter monotonicity, and optional agreement with
source/analysis/artifact integrity metadata. It does not prove that scenarios
are complete, findings are true, or a design is correct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable


ANALYSIS_VERSION = "simulate-analysis/v2"
ARRAY_KEYS = ("pending", "in_progress", "done", "failed")
MODE_CAPS = {
    "targeted": 8,
    "standard": 12,
    "deep": 20,
    "attacks-only": 12,
}
MODE_MINIMUMS = {
    "targeted": 4,
    "standard": 8,
    "deep": 12,
    "attacks-only": 6,
}
ROOT_KEYS = {
    "schema_version",
    "analysis_version",
    "spec_sha256",
    "analysis_sha256",
    "mode",
    "focus",
    "scenario_cap",
    "iteration",
    "status",
    "stop_reason",
    "next_counter",
    *ARRAY_KEYS,
}
SCENARIO_KEYS = {
    "id",
    "slug",
    "category",
    "title",
    "brief",
    "priority",
    "actors_involved",
    "transitions_targeted",
    "invariants_targeted",
    "attempts",
    "last_error",
    "artifact_path",
    "artifact_sha256",
}
ID_RE = re.compile(r"^[GEAF][0-9]{2,3}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
TRANSITION_RE = re.compile(r"^T[0-9]{2,3}$")
INVARIANT_RE = re.compile(r"^I[0-9]{2,3}$")
ARTIFACT_RE = re.compile(
    r"^sim-(?P<counter>[0-9]{3,})-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
ARTIFACT_TMP_RE = re.compile(
    r"^(?P<final>sim-(?P<counter>[0-9]{3,})-"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md)\.tmp$"
)
DECLARED_TRANSITIONS_LABEL = "Declared transition IDs"
DECLARED_INVARIANTS_LABEL = "Declared invariant IDs"


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _keys_error(value: dict[str, Any], expected: set[str], where: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        errors.append(f"{where}: missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"{where}: unsupported keys: {', '.join(extra)}")
    return errors


def _string_list(
    value: Any,
    where: str,
    *,
    minimum: int = 0,
    pattern: re.Pattern[str] | None = None,
) -> list[str]:
    if not isinstance(value, list):
        return [f"{where}: expected array"]
    errors: list[str] = []
    if len(value) < minimum:
        errors.append(f"{where}: expected at least {minimum} item(s)")
    if len(value) != len(set(item for item in value if isinstance(item, str))):
        errors.append(f"{where}: duplicate items are not allowed")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            errors.append(f"{where}[{index}]: expected non-empty string")
        elif pattern and not pattern.fullmatch(item):
            errors.append(f"{where}[{index}]: invalid value {item!r}")
    return errors


def _validate_scenario(value: Any, where: str, bucket: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}: expected object"]
    errors = _keys_error(value, SCENARIO_KEYS, where)

    scenario_id = value.get("id")
    if not isinstance(scenario_id, str) or not ID_RE.fullmatch(scenario_id):
        errors.append(f"{where}.id: expected zero-padded G/E/A/F id")

    slug = value.get("slug")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        errors.append(f"{where}.slug: expected lowercase kebab-case")

    category = value.get("category")
    if not isinstance(category, str) or category not in {"golden", "edge", "attack"}:
        errors.append(f"{where}.category: expected golden, edge, or attack")
    for field in ("title", "brief"):
        if not isinstance(value.get(field), str) or not value.get(field):
            errors.append(f"{where}.{field}: expected non-empty string")

    priority = value.get("priority")
    if not _is_int(priority) or priority not in {1, 2, 3}:
        errors.append(f"{where}.priority: expected integer 1..3 (1 is highest)")

    errors.extend(_string_list(value.get("actors_involved"), f"{where}.actors_involved", minimum=1))
    errors.extend(
        _string_list(
            value.get("transitions_targeted"),
            f"{where}.transitions_targeted",
            minimum=1,
            pattern=TRANSITION_RE,
        )
    )
    errors.extend(
        _string_list(
            value.get("invariants_targeted"),
            f"{where}.invariants_targeted",
            pattern=INVARIANT_RE,
        )
    )

    attempts = value.get("attempts")
    if not _is_int(attempts) or attempts < 0:
        errors.append(f"{where}.attempts: expected non-negative integer")
    elif bucket == "pending" and attempts != 0:
        errors.append(f"{where}.attempts: pending scenarios require 0")
    elif bucket in {"in_progress", "done", "failed"} and attempts < 1:
        errors.append(f"{where}.attempts: {bucket} scenarios require at least 1")
    last_error = value.get("last_error")
    if last_error is not None and (not isinstance(last_error, str) or not last_error.strip()):
        errors.append(f"{where}.last_error: expected null or non-empty string")
    if bucket == "failed" and not isinstance(last_error, str):
        errors.append(f"{where}.last_error: failed scenarios require an error")
    if bucket in {"pending", "in_progress", "done"} and last_error is not None:
        errors.append(f"{where}.last_error: {bucket} scenarios must clear the error")

    artifact_path = value.get("artifact_path")
    artifact_sha256 = value.get("artifact_sha256")
    if artifact_path is not None and (
        not isinstance(artifact_path, str) or not ARTIFACT_RE.fullmatch(artifact_path)
    ):
        errors.append(f"{where}.artifact_path: expected a safe sim-NNN-slug.md basename or null")
    if artifact_sha256 is not None and (
        not isinstance(artifact_sha256, str) or not DIGEST_RE.fullmatch(artifact_sha256)
    ):
        errors.append(f"{where}.artifact_sha256: expected 64 lowercase hex characters or null")
    artifact_match = ARTIFACT_RE.fullmatch(artifact_path) if isinstance(artifact_path, str) else None
    if artifact_match and isinstance(slug, str) and artifact_match.group("slug") != slug:
        errors.append(
            f"{where}.artifact_path: filename suffix must match scenario slug {slug!r}"
        )
    if bucket == "pending" and (artifact_path is not None or artifact_sha256 is not None):
        errors.append(f"{where}: pending scenarios must not claim an artifact")
    if bucket == "in_progress":
        if not isinstance(artifact_path, str):
            errors.append(f"{where}: in_progress requires a reserved artifact_path")
        if artifact_sha256 is not None:
            errors.append(f"{where}: in_progress artifact_sha256 must remain null")
    if bucket == "done":
        if not isinstance(artifact_path, str) or not isinstance(artifact_sha256, str):
            errors.append(f"{where}: done requires artifact_path and artifact_sha256")
    if bucket == "failed":
        if not isinstance(artifact_path, str):
            errors.append(f"{where}: failed requires its reserved artifact_path")
        if artifact_sha256 is not None:
            errors.append(f"{where}: failed artifact_sha256 must remain null")
    return errors


def _artifact_counter(path: str) -> int | None:
    match = ARTIFACT_RE.fullmatch(path)
    return int(match.group("counter")) if match else None


def _scenario_order(value: dict[str, Any]) -> tuple[int, str]:
    priority = value.get("priority")
    scenario_id = value.get("id")
    return (
        priority if _is_int(priority) else 999,
        scenario_id if isinstance(scenario_id, str) else "~",
    )


def validate_v2(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["queue: expected top-level object"]
    errors = _keys_error(data, ROOT_KEYS, "queue")

    if not _is_int(data.get("schema_version")) or data.get("schema_version") != 2:
        errors.append("queue.schema_version: only version 2 is writable/resumable")
    if data.get("analysis_version") != ANALYSIS_VERSION:
        errors.append(f"queue.analysis_version: expected {ANALYSIS_VERSION!r}")
    digest = data.get("spec_sha256")
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        errors.append("queue.spec_sha256: expected 64 lowercase hex characters")
    analysis_digest = data.get("analysis_sha256")
    if not isinstance(analysis_digest, str) or not DIGEST_RE.fullmatch(analysis_digest):
        errors.append("queue.analysis_sha256: expected 64 lowercase hex characters")

    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in MODE_CAPS:
        errors.append("queue.mode: unsupported mode")
    focus = data.get("focus")
    if focus is not None and (not isinstance(focus, str) or not focus.strip()):
        errors.append("queue.focus: expected null or non-empty string")
    if mode == "targeted" and not isinstance(focus, str):
        errors.append("queue.focus: targeted mode requires a focus")

    cap = data.get("scenario_cap")
    if not _is_int(cap):
        errors.append("queue.scenario_cap: expected integer")
    elif isinstance(mode, str) and mode in MODE_CAPS and cap != MODE_CAPS[mode]:
        errors.append(f"queue.scenario_cap: {mode} mode requires {MODE_CAPS[mode]}")

    for field in ("iteration", "next_counter"):
        value = data.get(field)
        minimum = 0 if field == "iteration" else 1
        if not _is_int(value) or value < minimum:
            errors.append(f"queue.{field}: expected integer >= {minimum}")

    status = data.get("status")
    stop_reason = data.get("stop_reason")
    complete_reasons = {
        "scenario inventory exhausted",
        "mode scenario cap reached",
        "focus inventory exhausted",
    }
    halted_reasons = {"no progress", "hard error"}
    if stop_reason is not None and not isinstance(stop_reason, str):
        errors.append("queue.stop_reason: expected null or supported string")
    if status == "active":
        if stop_reason is not None:
            errors.append("queue.stop_reason: active queue requires null")
    elif status == "complete":
        if not isinstance(stop_reason, str) or stop_reason not in complete_reasons:
            errors.append("queue.stop_reason: invalid complete reason")
    elif status == "halted":
        if not isinstance(stop_reason, str) or stop_reason not in halted_reasons:
            errors.append("queue.stop_reason: invalid halted reason")
    else:
        errors.append("queue.status: expected active, complete, or halted")

    all_scenarios: list[tuple[str, int, dict[str, Any]]] = []
    for bucket in ARRAY_KEYS:
        values = data.get(bucket)
        if not isinstance(values, list):
            errors.append(f"queue.{bucket}: expected array")
            continue
        for index, scenario in enumerate(values):
            errors.extend(_validate_scenario(scenario, f"queue.{bucket}[{index}]", bucket))
            if isinstance(scenario, dict):
                all_scenarios.append((bucket, index, scenario))
        if all(isinstance(item, dict) for item in values):
            expected = sorted(values, key=_scenario_order)
            if values != expected:
                errors.append(f"queue.{bucket}: expected priority ASC, id ASC order")

    ids: dict[str, str] = {}
    slugs: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}
    artifact_counters: list[int] = []
    for bucket, index, scenario in all_scenarios:
        where = f"queue.{bucket}[{index}]"
        scenario_id = scenario.get("id")
        slug = scenario.get("slug")
        if isinstance(scenario_id, str):
            if scenario_id in ids:
                errors.append(f"{where}.id: duplicate of {ids[scenario_id]}")
            else:
                ids[scenario_id] = where
        if isinstance(slug, str):
            if slug in slugs:
                errors.append(f"{where}.slug: duplicate of {slugs[slug]}")
            else:
                slugs[slug] = where
        artifact_path = scenario.get("artifact_path")
        if isinstance(artifact_path, str):
            counter = _artifact_counter(artifact_path)
            if counter is not None:
                artifact_counters.append(counter)
            if artifact_path in artifact_paths:
                errors.append(f"{where}.artifact_path: duplicate of {artifact_paths[artifact_path]}")
            else:
                artifact_paths[artifact_path] = where

    next_counter = data.get("next_counter")
    if artifact_counters and _is_int(next_counter) and next_counter <= max(artifact_counters):
        errors.append(
            "queue.next_counter: must be strictly greater than every reserved artifact prefix "
            f"(max={max(artifact_counters)})"
        )

    if _is_int(cap) and len(all_scenarios) > cap:
        errors.append(f"queue: {len(all_scenarios)} scenarios exceed cap {cap}")
    if isinstance(mode, str) and mode in MODE_MINIMUMS and len(all_scenarios) < MODE_MINIMUMS[mode]:
        errors.append(
            f"queue: {mode} mode requires at least {MODE_MINIMUMS[mode]} distinct scenarios"
        )
    if mode == "attacks-only":
        for bucket, index, scenario in all_scenarios:
            if scenario.get("category") == "golden":
                errors.append(f"queue.{bucket}[{index}].category: golden is forbidden in attacks-only mode")

    if isinstance(mode, str) and mode in {"standard", "deep"} and all_scenarios:
        negative_count = sum(
            scenario.get("category") in {"edge", "attack"}
            for _, _, scenario in all_scenarios
        )
        required_negative = (len(all_scenarios) * 3 + 9) // 10
        if negative_count < required_negative:
            errors.append(
                f"queue: {mode} mode requires at least 30% edge/attack scenarios "
                f"({required_negative} of {len(all_scenarios)})"
            )

    pending = data.get("pending")
    in_progress = data.get("in_progress")
    if status == "active" and not pending and not in_progress:
        errors.append("queue: active state requires pending or in_progress work")
    if status == "complete":
        if pending or in_progress:
            errors.append("queue: complete state requires empty pending/in_progress")
        if stop_reason == "focus inventory exhausted" and mode != "targeted":
            errors.append("queue: focus inventory exhausted is valid only in targeted mode")
        if stop_reason == "mode scenario cap reached" and (
            not _is_int(cap) or len(all_scenarios) != cap
        ):
            errors.append("queue: mode cap completion requires exactly scenario_cap scenarios")
    return errors


def validate_legacy_v1(data: Any) -> list[str]:
    """Check only enough legacy shape to inspect safely; v1 is never resumable."""
    if not isinstance(data, dict):
        return ["legacy queue: expected top-level object"]
    required = {"version", "next_counter", "pending", "in_progress", "done"}
    errors: list[str] = []
    missing = sorted(required - set(data))
    if missing:
        errors.append(f"legacy queue: missing keys: {', '.join(missing)}")
    if data.get("version") != 1:
        errors.append("legacy queue.version: expected 1")
    if not _is_int(data.get("next_counter")) or data.get("next_counter", 0) < 1:
        errors.append("legacy queue.next_counter: expected integer >= 1")
    for bucket in ("pending", "in_progress", "done"):
        values = data.get(bucket)
        if not isinstance(values, list):
            errors.append(f"legacy queue.{bucket}: expected array")
            continue
        for index, scenario in enumerate(values):
            where = f"legacy queue.{bucket}[{index}]"
            if not isinstance(scenario, dict):
                errors.append(f"{where}: expected object")
                continue
            for field in ("id", "slug", "category", "title", "brief", "priority"):
                if field not in scenario:
                    errors.append(f"{where}: missing {field}")
    return errors


def _spec_sha256(path: Path) -> str:
    text = path.read_bytes().decode("utf-8")
    normalized = unicodedata.normalize(
        "NFC", text.replace("\r\n", "\n").replace("\r", "\n")
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _metadata(text: str, label: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(label)}:\s*(\S.*?)\s*$", text)
    return match.group(1).strip() if match else None


def _parse_declared_ids(
    text: str,
    label: str,
    pattern: re.Pattern[str],
    *,
    allow_none: bool,
) -> tuple[set[str], list[str]]:
    """Parse one canonical `Label: ID01, ID02` declaration line."""
    matches = re.findall(rf"(?m)^{re.escape(label)}:\s*(.*?)\s*$", text)
    if len(matches) != 1:
        return set(), [f"analysis: expected exactly one {label!r} declaration line"]
    raw = matches[0]
    if raw == "none":
        if allow_none:
            return set(), []
        return set(), [f"analysis: {label} cannot be none"]
    if not raw:
        return set(), [f"analysis: {label} cannot be empty; use 'none' when allowed"]
    raw_parts = raw.split(",")
    tokens = [part.strip() for part in raw_parts]
    errors: list[str] = []
    if ", ".join(tokens) != raw:
        errors.append(f"analysis: {label} must use canonical comma-space separators")
    invalid = [token for token in tokens if not pattern.fullmatch(token)]
    if invalid:
        errors.append(f"analysis: {label} has invalid ids: {', '.join(invalid)}")
    if len(tokens) != len(set(tokens)):
        errors.append(f"analysis: {label} contains duplicate ids")
    expected = sorted(tokens, key=lambda token: (int(token[1:]), token) if pattern.fullmatch(token) else (10**9, token))
    if tokens != expected:
        errors.append(f"analysis: {label} must be in numeric ascending order")
    return set(tokens) if not errors else set(), errors


def _validate_declared_references(
    data: dict[str, Any], declared_transitions: set[str], declared_invariants: set[str]
) -> list[str]:
    errors: list[str] = []
    for bucket in ARRAY_KEYS:
        for index, scenario in enumerate(data.get(bucket, [])):
            if not isinstance(scenario, dict):
                continue
            for field, declared in (
                ("transitions_targeted", declared_transitions),
                ("invariants_targeted", declared_invariants),
            ):
                refs = scenario.get(field)
                if not isinstance(refs, list):
                    continue
                unknown = sorted(ref for ref in refs if isinstance(ref, str) and ref not in declared)
                if unknown:
                    errors.append(
                        f"queue.{bucket}[{index}].{field}: undeclared analysis ids: "
                        + ", ".join(unknown)
                    )
    return errors


def validate_external(
    data: dict[str, Any],
    spec: Path | None,
    analysis: Path | None,
    artifacts_dir: Path | None,
    *,
    resume: bool,
) -> tuple[list[str], str, str, str]:
    errors: list[str] = []
    digest_state = "unverified"
    analysis_state = "unverified"
    artifacts_state = "unverified"
    if spec is not None:
        actual = _spec_sha256(spec)
        digest_state = "matched" if data.get("spec_sha256") == actual else "mismatched"
        if digest_state == "mismatched":
            errors.append(f"spec digest mismatch: queue={data.get('spec_sha256')} actual={actual}")
    declared_transitions: set[str] | None = None
    declared_invariants: set[str] | None = None
    if analysis is not None:
        text = analysis.read_text(encoding="utf-8")
        actual_analysis_digest = _spec_sha256(analysis)
        analysis_digest_matches = data.get("analysis_sha256") == actual_analysis_digest
        if not analysis_digest_matches:
            errors.append(
                "analysis digest mismatch: "
                f"queue={data.get('analysis_sha256')} actual={actual_analysis_digest}"
            )
        expected = {
            "Spec SHA-256": data.get("spec_sha256"),
            "Analysis version": data.get("analysis_version"),
            "Queue schema": str(data.get("schema_version")),
            "Mode": data.get("mode"),
        }
        mismatches = []
        for label, expected_value in expected.items():
            actual_value = _metadata(text, label)
            if actual_value != expected_value:
                mismatches.append(f"{label}={actual_value!r}, expected {expected_value!r}")
        analysis_state = "matched" if not mismatches and analysis_digest_matches else "mismatched"
        errors.extend(f"analysis metadata mismatch: {item}" for item in mismatches)
        if analysis_digest_matches and not mismatches:
            declared_transitions, transition_errors = _parse_declared_ids(
                text,
                DECLARED_TRANSITIONS_LABEL,
                TRANSITION_RE,
                allow_none=False,
            )
            declared_invariants, invariant_errors = _parse_declared_ids(
                text,
                DECLARED_INVARIANTS_LABEL,
                INVARIANT_RE,
                allow_none=True,
            )
            errors.extend(transition_errors)
            errors.extend(invariant_errors)
            if not transition_errors and not invariant_errors:
                errors.extend(
                    _validate_declared_references(
                        data, declared_transitions, declared_invariants
                    )
                )
    if artifacts_dir is not None:
        artifact_errors: list[str] = []
        bound: dict[str, tuple[str, dict[str, Any]]] = {}
        for bucket in ARRAY_KEYS:
            for scenario in data.get(bucket, []):
                if not isinstance(scenario, dict):
                    continue
                artifact_path = scenario.get("artifact_path")
                if isinstance(artifact_path, str) and ARTIFACT_RE.fullmatch(artifact_path):
                    bound[artifact_path] = (bucket, scenario)

        try:
            entries = [entry for entry in artifacts_dir.iterdir() if entry.is_file()]
        except OSError as exc:
            return (
                errors + [f"cannot list artifacts directory: {exc}"],
                digest_state,
                analysis_state,
                "mismatched",
            )

        finals: dict[str, Path] = {}
        temporaries: dict[str, tuple[Path, str]] = {}
        disk_counters: list[int] = []
        for entry in entries:
            final_match = ARTIFACT_RE.fullmatch(entry.name)
            if final_match:
                finals[entry.name] = entry
                disk_counters.append(int(final_match.group("counter")))
                continue
            temp_match = ARTIFACT_TMP_RE.fullmatch(entry.name)
            if temp_match:
                temporaries[entry.name] = (entry, temp_match.group("final"))
                disk_counters.append(int(temp_match.group("counter")))

        next_counter = data.get("next_counter")
        if disk_counters and _is_int(next_counter) and next_counter <= max(disk_counters):
            artifact_errors.append(
                "queue.next_counter: must be strictly greater than every on-disk scenario prefix "
                f"(max={max(disk_counters)})"
            )

        for name in sorted(finals):
            if name not in bound:
                artifact_errors.append(
                    f"unbound final artifact {name}; preserve it for reconciliation"
                )
        for name, (_, final_name) in sorted(temporaries.items()):
            binding = bound.get(final_name)
            if binding is None:
                artifact_errors.append(
                    f"unbound temporary artifact {name}; preserve it for reconciliation"
                )
            else:
                bucket, scenario = binding
                artifact_errors.append(
                    f"temporary artifact {name} is bound to {bucket} "
                    f"{scenario.get('id')}; preserve it for reconciliation"
                )

        for artifact_path, (bucket, scenario) in sorted(bound.items()):
            scenario_id = scenario.get("id")
            path = finals.get(artifact_path)
            if path is None:
                if bucket == "done":
                    artifact_errors.append(
                        f"{scenario_id}: cannot read {artifact_path}: final artifact is missing"
                    )
                elif bucket == "in_progress" and resume and not any(
                    final_name == artifact_path for _, final_name in temporaries.values()
                ):
                    artifact_errors.append(
                        f"{scenario_id}: in_progress reservation {artifact_path} has no artifact; "
                        "preserve the reservation and reconcile explicitly"
                    )
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                artifact_errors.append(f"{scenario_id}: cannot read {artifact_path}: {exc}")
                continue
            lines = text.splitlines()
            expected_header = f"# {scenario_id} - {scenario.get('title')}"
            if not lines or lines[0] != expected_header:
                artifact_errors.append(
                    f"{scenario_id}: {artifact_path} header must be exactly {expected_header!r}"
                )
            nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
            expected_sentinel = f"<!-- simulate-complete:{scenario_id} -->"
            if not nonempty_lines or nonempty_lines[-1] != expected_sentinel:
                artifact_errors.append(
                    f"{scenario_id}: {artifact_path} lacks final completion sentinel"
                )
            actual = _spec_sha256(path)
            if bucket == "done" and scenario.get("artifact_sha256") != actual:
                artifact_errors.append(
                    f"{scenario_id}: artifact digest mismatch for {artifact_path}"
                )
            if declared_transitions is not None:
                unknown = sorted(
                    set(re.findall(r"\bT[0-9]{2,3}\b", text)) - declared_transitions
                )
                if unknown:
                    artifact_errors.append(
                        f"{scenario_id}: {artifact_path} references undeclared transition ids: "
                        + ", ".join(unknown)
                    )
            if declared_invariants is not None:
                unknown = sorted(
                    set(re.findall(r"\bI[0-9]{2,3}\b", text)) - declared_invariants
                )
                if unknown:
                    artifact_errors.append(
                        f"{scenario_id}: {artifact_path} references undeclared invariant ids: "
                        + ", ".join(unknown)
                    )
            if bucket in {"in_progress", "failed"}:
                artifact_errors.append(
                    f"{scenario_id}: {bucket} has final artifact {artifact_path}; "
                    "preserve it and reconcile the queue explicitly"
                )
        errors.extend(artifact_errors)
        artifacts_state = "matched" if not artifact_errors else "mismatched"
    return errors, digest_state, analysis_state, artifacts_state


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _print_errors(errors: Iterable[str]) -> None:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", nargs="?", type=Path, help="path to _queue.json")
    parser.add_argument("--spec", type=Path, help="source spec to hash and compare")
    parser.add_argument("--analysis", type=Path, help="_analysis.md metadata to compare")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        help="directory containing completed scenario artifacts to verify",
    )
    parser.add_argument(
        "--allow-legacy-read",
        action="store_true",
        help="validate limited v1 shape for read-only inspection; never permits resume",
    )
    parser.add_argument(
        "--print-spec-sha256",
        type=Path,
        help="print the portable normalized UTF-8 digest and exit",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="require spec, analysis, and completed-artifact integrity checks",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_spec_sha256 is not None:
        try:
            print(_spec_sha256(args.print_spec_sha256))
        except (OSError, UnicodeError) as exc:
            print(f"ERROR: cannot hash spec: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.queue is None:
        print("ERROR: queue path is required unless --print-spec-sha256 is used", file=sys.stderr)
        return 2
    if args.resume and (
        args.spec is None or args.analysis is None or args.artifacts_dir is None
    ):
        print(
            "ERROR: --resume requires --spec, --analysis, and --artifacts-dir",
            file=sys.stderr,
        )
        return 2
    try:
        data = _load(args.queue)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read JSON: {exc}", file=sys.stderr)
        return 1

    is_legacy = isinstance(data, dict) and "schema_version" not in data and data.get("version") == 1
    if is_legacy:
        if not args.allow_legacy_read:
            print(
                "ERROR: legacy queue v1 is read-only and not resumable; preserve it and use a fresh --out "
                "(or pass --allow-legacy-read for limited inspection)",
                file=sys.stderr,
            )
            return 1
        errors = validate_legacy_v1(data)
        if errors:
            _print_errors(errors)
            return 1
        print(f"VALID legacy queue-v1 (read-only; not resumable): {args.queue}")
        return 0

    errors = validate_v2(data)
    digest_state = "unverified"
    analysis_state = "unverified"
    artifacts_state = "unverified"
    if isinstance(data, dict):
        try:
            external_errors, digest_state, analysis_state, artifacts_state = validate_external(
                data,
                args.spec,
                args.analysis,
                args.artifacts_dir,
                resume=args.resume,
            )
            errors.extend(external_errors)
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read comparison artifact: {exc}")
    if errors:
        _print_errors(errors)
        return 1

    print(
        f"VALID queue-v2: {args.queue} "
        f"(shape/order/uniqueness; digest={digest_state}; analysis={analysis_state}; "
        f"artifacts={artifacts_state})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
