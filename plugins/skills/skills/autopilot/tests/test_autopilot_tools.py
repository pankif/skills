from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_bus = load_module("validate_bus", SKILL_ROOT / "scripts" / "validate_bus.py")
check_unfinished = load_module(
    "check_unfinished", SKILL_ROOT / "scripts" / "check_unfinished.py"
)


class BusValidatorTests(unittest.TestCase):
    def test_valid_fixture(self) -> None:
        record = validate_bus.load_record(SKILL_ROOT / "fixtures" / "bus" / "valid.json")
        self.assertEqual(validate_bus.validate_record(record), [])

    def test_unsupported_version_fails_closed(self) -> None:
        record = validate_bus.load_record(
            SKILL_ROOT / "fixtures" / "bus" / "unsupported-version.json"
        )
        errors = validate_bus.validate_record(record)
        self.assertTrue(any("unsupported schema_version" in error for error in errors))

    def test_schema_version_requires_an_integer(self) -> None:
        for invalid in (True, 2.0):
            with self.subTest(invalid=invalid):
                record = validate_bus.load_record(
                    SKILL_ROOT / "fixtures" / "bus" / "valid.json"
                )
                record["schema_version"] = invalid
                errors = validate_bus.validate_record(record)
            self.assertTrue(any("unsupported schema_version" in error for error in errors))

    def test_unknown_disclosure_reference_is_rejected(self) -> None:
        record = validate_bus.load_record(
            SKILL_ROOT / "fixtures" / "bus" / "bad-reference.json"
        )
        errors = validate_bus.validate_record(record, check_digest=False)
        self.assertTrue(any("unknown decisions" in error for error in errors))

    def test_modified_sealed_record_fails_integrity(self) -> None:
        record = validate_bus.load_record(SKILL_ROOT / "fixtures" / "bus" / "valid.json")
        record["target"] = "tampered"
        errors = validate_bus.validate_record(record)
        self.assertTrue(any("canonical record content" in error for error in errors))

    def test_seal_round_trip(self) -> None:
        source = validate_bus.load_record(SKILL_ROOT / "fixtures" / "bus" / "valid.json")
        source["integrity"]["canonical_sha256"] = validate_bus.ZERO_DIGEST
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "BUS.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            self.assertEqual(validate_bus.main([str(path), "--seal"]), 0)
            self.assertEqual(validate_bus.validate_record(validate_bus.load_record(path)), [])

    def test_unknown_root_field_is_rejected(self) -> None:
        record = validate_bus.load_record(SKILL_ROOT / "fixtures" / "bus" / "valid.json")
        record["unexpected"] = True
        record["integrity"]["canonical_sha256"] = validate_bus.canonical_digest(record)
        errors = validate_bus.validate_record(record)
        self.assertTrue(any("unknown fields" in error for error in errors))

    def test_authority_binds_action_to_target_and_rejects_deploy(self) -> None:
        record = validate_bus.load_record(SKILL_ROOT / "fixtures" / "bus" / "valid.json")
        record["outward_authority"] = [
            {
                "action": "deploy",
                "target": "production",
                "current_request_evidence": "deploy it",
            }
        ]
        record["integrity"]["canonical_sha256"] = validate_bus.canonical_digest(record)
        errors = validate_bus.validate_record(record)
        self.assertTrue(any("unsupported value" in error for error in errors))

    def test_prompt_normalization_is_portable(self) -> None:
        self.assertEqual(
            validate_bus.prompt_digest("cafe\u0301\r\nnext"),
            validate_bus.prompt_digest("caf\u00e9\nnext"),
        )


class MarkerTests(unittest.TestCase):
    def test_marker_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.py"
            path.write_text("raise RuntimeError('TODO(autopilot:X)')\n", encoding="utf-8")
            findings = check_unfinished.find_markers([path], list(check_unfinished.DEFAULT_PATTERNS))
            self.assertEqual(len(findings), 1)

    def test_clean_file_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "module.py"
            path.write_text("print('done')\n", encoding="utf-8")
            findings = check_unfinished.find_markers([path], list(check_unfinished.DEFAULT_PATTERNS))
            self.assertEqual(findings, [])

    def test_unreadable_utf8_makes_scan_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary.dat"
            path.write_bytes(b"\xff\xfe\x00")
            findings, skipped = check_unfinished.scan_markers(
                [path], list(check_unfinished.DEFAULT_PATTERNS)
            )
            self.assertEqual(findings, [])
            self.assertEqual(len(skipped), 1)

    def test_explicit_build_directory_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "build"
            root.mkdir()
            (root / "generated.txt").write_text(
                "TODO(autopilot:explicit-root)\n", encoding="utf-8"
            )
            findings, skipped = check_unfinished.scan_markers(
                [root], list(check_unfinished.DEFAULT_PATTERNS)
            )
            self.assertEqual(len(findings), 1)
            self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
