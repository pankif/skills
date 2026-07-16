from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "validate_case.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ValidateCaseTests(unittest.TestCase):
    def run_validator(self, *args: Path) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(SCRIPT), *(str(arg) for arg in args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

    def test_accepts_valid_v1_fixture(self) -> None:
        result = self.run_validator(FIXTURES / "valid-case-v1.jsonl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VALID CASE schema v1 / analysis v1", result.stdout)

    def test_legacy_case_fails_closed(self) -> None:
        result = self.run_validator(FIXTURES / "legacy-case.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unversioned/legacy", result.stderr)

    def test_unknown_version_fails_closed(self) -> None:
        result = self.run_validator(FIXTURES / "unsupported-case-v2.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported schema_version", result.stderr)

    def test_missing_analysis_version_fails_closed(self) -> None:
        result = self.run_validator(FIXTURES / "missing-analysis-version-case-v1.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("analysis_version", result.stderr)

    def test_unknown_analysis_version_fails_closed(self) -> None:
        result = self.run_validator(FIXTURES / "unsupported-analysis-version-case-v1.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported analysis_version", result.stderr)

    def test_header_timestamp_requires_rfc3339_timezone(self) -> None:
        result = self.run_validator(FIXTURES / "naive-header-timestamp-case-v1.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RFC3339", result.stderr)

    def test_event_timestamp_requires_rfc3339_timezone(self) -> None:
        result = self.run_validator(FIXTURES / "naive-event-timestamp-case-v1.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RFC3339", result.stderr)

    def test_sequence_gap_is_rejected(self) -> None:
        result = self.run_validator(FIXTURES / "sequence-gap-case-v1.jsonl")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sequence must be contiguous", result.stderr)

    def test_previous_snapshot_allows_only_append(self) -> None:
        previous = (FIXTURES / "valid-case-v1.jsonl").read_text(encoding="utf-8")
        appended = previous + (
            '{"schema":"diagnose.case","schema_version":1,"record_type":"terminal",'
            '"case_id":"case-valid","sequence":3,"timestamp":"2026-07-17T10:00:03Z",'
            '"payload":{"terminal":"NARROWED"}}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_path = root / "previous.jsonl"
            candidate_path = root / "candidate.jsonl"
            previous_path.write_text(previous, encoding="utf-8")
            candidate_path.write_text(appended, encoding="utf-8")
            result = self.run_validator(candidate_path, Path("--previous"), previous_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("append-safe", result.stdout)

    def test_previous_snapshot_rejects_rewrite(self) -> None:
        previous = (FIXTURES / "valid-case-v1.jsonl").read_text(encoding="utf-8")
        rewritten = previous.replace('"oracle_state":"trusted"', '"oracle_state":"contested"')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_path = root / "previous.jsonl"
            candidate_path = root / "candidate.jsonl"
            previous_path.write_text(previous, encoding="utf-8")
            candidate_path.write_text(rewritten, encoding="utf-8")
            result = self.run_validator(candidate_path, Path("--previous"), previous_path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not an append-only extension", result.stderr)


if __name__ == "__main__":
    unittest.main()
