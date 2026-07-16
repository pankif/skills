#!/usr/bin/env python3
"""Run cross-platform structural checks for the public skills repository.

The checks are intentionally narrow. A pass means repository metadata,
frontmatter, `SKILL.md` local references, machine-readable artifacts, and
deterministic validator tests are internally well formed. It is not a
behavioral eval.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "skills"
SKILLS_ROOT = PLUGIN_ROOT / "skills"
CORE_SKILLS = {"autopilot", "spec", "simulate", "diagnose"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
LOCAL_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"((?:\.\./)*"
    r"(?:references|scripts|schemas|agents|fixtures|evals|docs)/"
    r"[A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+)"
)


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.notes: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)


def load_json(path: Path, validation: Validation) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        validation.errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None


def parse_frontmatter(path: Path, validation: Validation) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        validation.errors.append(f"{path.relative_to(ROOT)}: missing YAML frontmatter")
        return "", "", text
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        validation.errors.append(f"{path.relative_to(ROOT)}: unclosed YAML frontmatter")
        return "", "", text

    fields: dict[str, str] = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line or line[0].isspace() or ":" not in line:
            index += 1
            continue
        key, raw = line.split(":", 1)
        value = raw.strip()
        if value in {">", ">-", "|", "|-"}:
            chunks: list[str] = []
            index += 1
            while index < end and (not lines[index] or lines[index][0].isspace()):
                chunks.append(lines[index].strip())
                index += 1
            fields[key.strip()] = " ".join(chunk for chunk in chunks if chunk)
            continue
        fields[key.strip()] = value.strip("\"'")
        index += 1
    return fields.get("name", ""), fields.get("description", ""), text


def validate_local_references(skill_dir: Path, text: str, validation: Validation) -> None:
    for raw in sorted(set(LOCAL_REF_RE.findall(text))):
        candidate = (skill_dir / raw).resolve()
        try:
            candidate.relative_to(ROOT.resolve())
        except ValueError:
            validation.errors.append(
                f"{skill_dir.relative_to(ROOT)}/SKILL.md: reference escapes repository: {raw}"
            )
            continue
        validation.require(
            candidate.exists(),
            f"{skill_dir.relative_to(ROOT)}/SKILL.md: missing local reference {raw}",
        )


def validate_openai_yaml(path: Path, validation: Validation) -> None:
    if not path.exists():
        validation.errors.append(f"{path.relative_to(ROOT)}: missing Codex skill metadata")
        return
    text = path.read_text(encoding="utf-8")
    required_patterns = {
        "interface": r"(?m)^interface:\s*$",
        "display_name": r"(?m)^\s+display_name:\s*\S",
        "short_description": r"(?m)^\s+short_description:\s*\S",
        "policy": r"(?m)^policy:\s*$",
        "allow_implicit_invocation": r"(?m)^\s+allow_implicit_invocation:\s*(true|false)\s*$",
    }
    for label, pattern in required_patterns.items():
        validation.require(
            re.search(pattern, text) is not None,
            f"{path.relative_to(ROOT)}: missing or malformed {label}",
        )


def validate_eval_catalog(skill_dir: Path, validation: Validation) -> None:
    path = skill_dir / "evals" / "evals.json"
    if not path.exists():
        validation.errors.append(f"{path.relative_to(ROOT)}: missing public eval catalog")
        return
    data = load_json(path, validation)
    if not isinstance(data, dict):
        return
    skill_name = skill_dir.name
    validation.require(
        data.get("schema_version") == 1,
        f"{path.relative_to(ROOT)}: schema_version must be 1",
    )
    evaluation_version = data.get("evaluation_version")
    validation.require(
        isinstance(evaluation_version, int)
        and not isinstance(evaluation_version, bool)
        and evaluation_version >= 1,
        f"{path.relative_to(ROOT)}: evaluation_version must be a positive integer",
    )
    validation.require(
        data.get("skill_name") == skill_name,
        f"{path.relative_to(ROOT)}: skill_name must be {skill_name!r}",
    )
    cases = data.get("evals")
    if not isinstance(cases, list) or not cases:
        validation.errors.append(f"{path.relative_to(ROOT)}: evals must be a non-empty array")
        return
    ids: list[Any] = []
    names: list[str] = []
    has_trigger = False
    has_non_trigger = False
    for index, case in enumerate(cases):
        prefix = f"{path.relative_to(ROOT)}: evals[{index}]"
        if not isinstance(case, dict):
            validation.errors.append(f"{prefix} must be an object")
            continue
        ids.append(case.get("id"))
        name = case.get("name")
        if not isinstance(name, str) or not name:
            validation.errors.append(f"{prefix}.name must be a non-empty string")
        else:
            names.append(name)
        should_trigger = case.get("should_trigger")
        if not isinstance(should_trigger, bool):
            validation.errors.append(f"{prefix}.should_trigger must be boolean")
        else:
            has_trigger = has_trigger or should_trigger
            has_non_trigger = has_non_trigger or not should_trigger
        for field in ("prompt", "expected_output"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                validation.errors.append(f"{prefix}.{field} must be a non-empty string")
        if not isinstance(case.get("files"), list):
            validation.errors.append(f"{prefix}.files must be an array")
    validation.require(len(ids) == len(set(ids)), f"{path.relative_to(ROOT)}: eval IDs must be unique")
    validation.require(
        len(names) == len(set(names)), f"{path.relative_to(ROOT)}: eval names must be unique"
    )
    validation.require(has_trigger, f"{path.relative_to(ROOT)}: needs a trigger case")
    validation.require(has_non_trigger, f"{path.relative_to(ROOT)}: needs a non-trigger case")


def validate_skills(validation: Validation) -> None:
    validation.require(
        SKILLS_ROOT.is_dir(), "plugins/skills/skills directory is missing"
    )
    if not SKILLS_ROOT.is_dir():
        return
    discovered = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
    validation.require(
        CORE_SKILLS <= discovered,
        "missing core skills: " + ", ".join(sorted(CORE_SKILLS - discovered)),
    )
    for skill_dir in sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        validation.require(
            skill_file.exists(), f"{skill_dir.relative_to(ROOT)}: missing SKILL.md"
        )
        if not skill_file.exists():
            continue
        name, description, text = parse_frontmatter(skill_file, validation)
        validation.require(
            name == skill_dir.name,
            f"{skill_file.relative_to(ROOT)}: name {name!r} must match directory {skill_dir.name!r}",
        )
        validation.require(
            NAME_RE.fullmatch(name or "") is not None,
            f"{skill_file.relative_to(ROOT)}: invalid skill name {name!r}",
        )
        validation.require(
            bool(description), f"{skill_file.relative_to(ROOT)}: description is required"
        )
        validation.require(
            len(description) <= 1024,
            f"{skill_file.relative_to(ROOT)}: description is {len(description)} chars; max is 1024",
        )
        validate_local_references(skill_dir, text, validation)
        if skill_dir.name in CORE_SKILLS:
            validate_openai_yaml(skill_dir / "agents" / "openai.yaml", validation)
            validate_eval_catalog(skill_dir, validation)


def validate_all_json(validation: Validation) -> None:
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        load_json(path, validation)


def resolve_marketplace_path(raw: str) -> Path:
    # Codex resolves repo marketplace paths from the marketplace repository root.
    return (ROOT / raw).resolve()


def validate_manifests(validation: Validation) -> None:
    required = [
        ROOT / ".claude-plugin" / "marketplace.json",
        ROOT / ".agents" / "plugins" / "marketplace.json",
        PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
        PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
    ]
    for path in required:
        validation.require(path.exists(), f"{path.relative_to(ROOT)}: required manifest missing")
    if any(not path.exists() for path in required):
        return

    claude_market = load_json(required[0], validation)
    codex_market = load_json(required[1], validation)
    claude_plugin = load_json(required[2], validation)
    codex_plugin = load_json(required[3], validation)
    if not all(isinstance(item, dict) for item in (claude_market, codex_market, claude_plugin, codex_plugin)):
        return

    validation.require(
        claude_market.get("name") == "pankif",
        ".claude-plugin/marketplace.json: marketplace name must be 'pankif'",
    )
    claude_entries = claude_market.get("plugins")
    validation.require(
        isinstance(claude_entries, list) and len(claude_entries) == 1,
        ".claude-plugin/marketplace.json: expected one plugin entry",
    )
    if isinstance(claude_entries, list) and claude_entries:
        validation.require(
            claude_entries[0].get("source") == "./plugins/skills",
            ".claude-plugin/marketplace.json: source must be ./plugins/skills",
        )

    entries = codex_market.get("plugins")
    validation.require(
        isinstance(entries, list) and len(entries) == 1,
        ".agents/plugins/marketplace.json: expected one plugin entry",
    )
    if isinstance(entries, list) and entries:
        entry = entries[0]
        source = entry.get("source") if isinstance(entry, dict) else None
        raw_path = source.get("path") if isinstance(source, dict) else None
        validation.require(
            source == {"source": "local", "path": "./plugins/skills"},
            ".agents/plugins/marketplace.json: source must be local ./plugins/skills",
        )
        if isinstance(raw_path, str):
            validation.require(
                resolve_marketplace_path(raw_path) == PLUGIN_ROOT.resolve(),
                ".agents/plugins/marketplace.json: path does not resolve to plugins/skills/",
            )
        policy = entry.get("policy", {}) if isinstance(entry, dict) else {}
        validation.require(
            policy.get("installation") in {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"},
            ".agents/plugins/marketplace.json: invalid installation policy",
        )
        validation.require(
            policy.get("authentication") in {"ON_INSTALL", "ON_USE"},
            ".agents/plugins/marketplace.json: invalid authentication policy",
        )

    for label, manifest in (("Claude", claude_plugin), ("Codex", codex_plugin)):
        validation.require(manifest.get("name") == "skills", f"{label} plugin name must be 'skills'")
        version = manifest.get("version")
        validation.require(
            isinstance(version, str) and SEMVER_RE.fullmatch(version) is not None,
            f"{label} plugin version must be strict semver",
        )
    validation.require(
        claude_plugin.get("version") == codex_plugin.get("version"),
        "Claude and Codex plugin versions must match",
    )
    validation.require(
        PLUGIN_ROOT.name == codex_plugin.get("name"),
        "Codex plugin folder name must match plugin manifest name",
    )
    if isinstance(entries, list) and entries:
        validation.require(
            entries[0].get("name") == codex_plugin.get("name"),
            "Codex marketplace entry name must match plugin manifest name",
        )
    validation.require(
        codex_plugin.get("skills") == "./skills/",
        "plugins/skills/.codex-plugin/plugin.json: skills must be './skills/'",
    )
    interface = codex_plugin.get("interface")
    validation.require(
        isinstance(interface, dict),
        "plugins/skills/.codex-plugin/plugin.json: interface object is required",
    )
    if isinstance(interface, dict):
        for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
            validation.require(
                isinstance(interface.get(field), str) and bool(interface[field].strip()),
                f"plugins/skills/.codex-plugin/plugin.json: interface.{field} is required",
            )


def run_unit_tests(validation: Validation) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for skill_name in sorted(CORE_SKILLS):
        tests = SKILLS_ROOT / skill_name / "tests"
        validation.require(tests.is_dir(), f"{tests.relative_to(ROOT)}: tests directory missing")
        if not tests.is_dir():
            continue
        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(tests),
            "-p",
            "test_*.py",
            "-v",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode:
            validation.errors.append(
                f"{skill_name} unit tests failed:\n{completed.stdout.rstrip()}"
            )
        else:
            count = len(re.findall(r"^test_.* \.\.\. ok$", completed.stdout, re.MULTILINE))
            validation.notes.append(f"{skill_name}: {count} validator tests passed")


def main() -> int:
    validation = Validation()
    validate_manifests(validation)
    validate_skills(validation)
    validate_all_json(validation)
    run_unit_tests(validation)

    for note in validation.notes:
        print(f"PASS: {note}")
    if validation.errors:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"repository structural validation failed: {len(validation.errors)} error(s)")
        return 1
    print("repository structural validation passed")
    print("scope: syntax, structure, references, manifests, and deterministic validator tests only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
