#!/usr/bin/env python3
"""Create or validate a versioned spec scratch-run manifest.

The manifest binds scratch notes to exact normalized intent and a deterministic
source-tree fingerprint. This is a stale-state guard, not proof that the notes or
resulting specification are correct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
ANALYSIS_VERSION = "spec-run/v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
ROOT_KEYS = {
    "schema_version",
    "analysis_version",
    "skill",
    "slug",
    "mode",
    "intent",
    "intent_sha256",
    "created_at",
    "source_identity",
}
IDENTITY_KEYS = {
    "kind",
    "root_name",
    "remote_sha256",
    "commit",
    "worktree_sha256",
    "excluded_paths",
}


def normalized_text(value: str) -> str:
    return unicodedata.normalize(
        "NFC", value.replace("\r\n", "\n").replace("\r", "\n")
    )


def text_sha256(value: str) -> str:
    return hashlib.sha256(normalized_text(value).encode("utf-8")).hexdigest()


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _git_root(root: Path) -> Path | None:
    try:
        result = _run_git(root, "rev-parse", "--show-toplevel")
    except OSError:
        return None
    if result.returncode:
        return None
    return Path(result.stdout.decode("utf-8", "surrogateescape").strip()).resolve()


def _relative_exclusions(root: Path, paths: Iterable[Path]) -> list[str]:
    exclusions: list[str] = []
    for path in paths:
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root).as_posix().rstrip("/")
        except ValueError:
            continue
        if relative and relative not in exclusions:
            exclusions.append(relative)
    return sorted(exclusions)


def _excluded(relative: str, exclusions: list[str]) -> bool:
    return any(relative == item or relative.startswith(item + "/") for item in exclusions)


def _listed_paths(root: Path, git: bool) -> list[str]:
    if git:
        result = _run_git(root, "ls-files", "-co", "--exclude-standard", "-z")
        if result.returncode:
            raise OSError(result.stderr.decode("utf-8", "replace").strip())
        return sorted(
            item.decode("utf-8", "surrogateescape").replace("\\", "/")
            for item in result.stdout.split(b"\0")
            if item
        )
    paths: list[str] = []
    for candidate in root.rglob("*"):
        relative = candidate.relative_to(root)
        if ".git" in relative.parts:
            continue
        if candidate.is_file() or candidate.is_symlink():
            paths.append(relative.as_posix())
    return sorted(paths)


def tree_sha256(root: Path, exclusions: list[str], git: bool) -> str:
    digest = hashlib.sha256()
    for relative in _listed_paths(root, git):
        if _excluded(relative, exclusions):
            continue
        path = root / Path(relative)
        encoded_path = relative.encode("utf-8", "surrogateescape")
        digest.update(encoded_path + b"\0")
        if path.is_symlink():
            payload = os.readlink(path).encode("utf-8", "surrogateescape")
            digest.update(b"L" + hashlib.sha256(payload).digest())
        elif path.is_file():
            file_digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    file_digest.update(chunk)
            digest.update(b"F" + file_digest.digest())
        elif path.exists():
            digest.update(b"O")
        else:
            digest.update(b"D")
    return digest.hexdigest()


def source_identity(source_root: Path, excluded_paths: Iterable[Path]) -> dict[str, Any]:
    requested_root = source_root.resolve()
    repository_root = _git_root(requested_root)
    git = repository_root is not None
    root = repository_root or requested_root
    exclusions = _relative_exclusions(root, excluded_paths)
    remote_sha256: str | None = None
    commit: str | None = None
    if git:
        remote = _run_git(root, "config", "--get", "remote.origin.url")
        if remote.returncode == 0 and remote.stdout.strip():
            remote_sha256 = hashlib.sha256(remote.stdout.strip()).hexdigest()
        head = _run_git(root, "rev-parse", "HEAD")
        if head.returncode == 0 and head.stdout.strip():
            commit = head.stdout.decode("ascii", "strict").strip()
    return {
        "kind": "git" if git else "directory",
        "root_name": root.name,
        "remote_sha256": remote_sha256,
        "commit": commit,
        "worktree_sha256": tree_sha256(root, exclusions, git),
        "excluded_paths": exclusions,
    }


def _check_keys(value: dict[str, Any], expected: set[str], where: str) -> list[str]:
    errors: list[str] = []
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        errors.append(f"{where}: missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{where}: unsupported fields: {', '.join(unknown)}")
    return errors


def validate_manifest(
    data: Any,
    *,
    intent: str | None = None,
    current_identity: dict[str, Any] | None = None,
) -> list[str]:
    if not isinstance(data, dict):
        return ["manifest: expected object"]
    schema_version = data.get("schema_version")
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        return [
            f"manifest: unsupported schema_version {schema_version!r}; "
            "preserve scratch and restart or migrate explicitly"
        ]
    if data.get("analysis_version") != ANALYSIS_VERSION:
        return [
            f"manifest: unsupported analysis_version {data.get('analysis_version')!r}; "
            "preserve scratch"
        ]

    errors = _check_keys(data, ROOT_KEYS, "manifest")
    if data.get("skill") != "spec":
        errors.append("manifest.skill: expected 'spec'")
    if not isinstance(data.get("slug"), str) or not SLUG.fullmatch(data["slug"]):
        errors.append("manifest.slug: expected lowercase kebab-case")
    if data.get("mode") not in {"quick", "deep"}:
        errors.append("manifest.mode: expected quick or deep")
    stored_intent = data.get("intent")
    if not isinstance(stored_intent, str) or not stored_intent.strip():
        errors.append("manifest.intent: expected non-empty string")
    stored_intent_hash = data.get("intent_sha256")
    if not isinstance(stored_intent_hash, str) or not HEX64.fullmatch(stored_intent_hash):
        errors.append("manifest.intent_sha256: expected 64 lowercase hex characters")
    elif isinstance(stored_intent, str) and stored_intent_hash != text_sha256(stored_intent):
        errors.append("manifest.intent_sha256: does not match stored intent")
    if intent is not None and stored_intent_hash != text_sha256(intent):
        errors.append("manifest.intent_sha256: does not match supplied original intent")

    created_at = data.get("created_at")
    if not isinstance(created_at, str) or not RFC3339.fullmatch(created_at):
        errors.append("manifest.created_at: expected RFC3339 date-time with timezone")
    else:
        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            errors.append("manifest.created_at: invalid date-time")

    identity = data.get("source_identity")
    if not isinstance(identity, dict):
        errors.append("manifest.source_identity: expected object")
    else:
        errors.extend(_check_keys(identity, IDENTITY_KEYS, "manifest.source_identity"))
        if identity.get("kind") not in {"git", "directory"}:
            errors.append("manifest.source_identity.kind: unsupported")
        if not isinstance(identity.get("root_name"), str) or not identity["root_name"]:
            errors.append("manifest.source_identity.root_name: expected non-empty string")
        for field in ("remote_sha256", "worktree_sha256"):
            value = identity.get(field)
            if field == "remote_sha256" and value is None:
                continue
            if not isinstance(value, str) or not HEX64.fullmatch(value):
                errors.append(f"manifest.source_identity.{field}: expected SHA-256 or null")
        commit = identity.get("commit")
        if commit is not None and (not isinstance(commit, str) or not commit):
            errors.append("manifest.source_identity.commit: expected non-empty string or null")
        exclusions = identity.get("excluded_paths")
        if not isinstance(exclusions, list) or any(
            not isinstance(item, str) or not item for item in exclusions
        ):
            errors.append("manifest.source_identity.excluded_paths: expected string array")
        elif len(exclusions) != len(set(exclusions)):
            errors.append("manifest.source_identity.excluded_paths: duplicates are forbidden")

        if current_identity is not None:
            for field in ("kind", "remote_sha256", "commit", "worktree_sha256"):
                if identity.get(field) != current_identity.get(field):
                    errors.append(f"manifest.source_identity.{field}: source drift detected")
            if identity.get("excluded_paths") != current_identity.get("excluded_paths"):
                errors.append("manifest.source_identity.excluded_paths: mismatch")
    return errors


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--slug")
    parser.add_argument("--mode", choices=("quick", "deep"))
    parser.add_argument("--intent-file", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--exclude", action="append", type=Path, default=[])
    args = parser.parse_args(argv)

    try:
        intent = args.intent_file.read_text(encoding="utf-8") if args.intent_file else None
        if args.initialize:
            if args.manifest.exists():
                print("run-invalid: manifest already exists; refusing overwrite", file=sys.stderr)
                return 1
            if not args.slug or not args.mode or intent is None or args.source_root is None:
                print(
                    "run-invalid: --initialize requires --slug, --mode, --intent-file, and --source-root",
                    file=sys.stderr,
                )
                return 2
            exclusions = [args.manifest.parent, *args.exclude]
            identity = source_identity(args.source_root, exclusions)
            data = {
                "schema_version": SCHEMA_VERSION,
                "analysis_version": ANALYSIS_VERSION,
                "skill": "spec",
                "slug": args.slug,
                "mode": args.mode,
                "intent": intent,
                "intent_sha256": text_sha256(intent),
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "source_identity": identity,
            }
            errors = validate_manifest(data, intent=intent, current_identity=identity)
            if errors:
                raise ValueError("; ".join(errors))
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        else:
            data = _load(args.manifest)

        current_identity = None
        if args.source_root is not None and isinstance(data, dict):
            stored = data.get("source_identity", {})
            stored_exclusions = stored.get("excluded_paths", []) if isinstance(stored, dict) else []
            root = _git_root(args.source_root.resolve()) or args.source_root.resolve()
            exclusion_paths = [root / Path(item) for item in stored_exclusions]
            current_identity = source_identity(args.source_root, exclusion_paths)
        errors = validate_manifest(data, intent=intent, current_identity=current_identity)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"run-invalid: {exc}", file=sys.stderr)
        return 1

    if errors:
        print(f"run-invalid: {args.manifest}", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"run-valid: {args.manifest}")
    print("note: identity/structure only; scratch content and spec semantics were not validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
