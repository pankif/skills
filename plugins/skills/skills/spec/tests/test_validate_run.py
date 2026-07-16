from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "validate_run.py"


class ValidateRunTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def initialize(self, root: Path) -> tuple[Path, Path]:
        source = root / "source"
        source.mkdir()
        (source / "app.txt").write_text("v1\n", encoding="utf-8")
        intent = root / "intent.md"
        intent.write_text("Define quiet hours.\n", encoding="utf-8")
        manifest = source / ".planning" / "spec" / "quiet-hours" / "_run.json"
        result = self.run_cli(
            str(manifest),
            "--initialize",
            "--slug",
            "quiet-hours",
            "--mode",
            "quick",
            "--intent-file",
            str(intent),
            "--source-root",
            str(source),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return manifest, intent

    def test_initialize_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, intent = self.initialize(root)
            result = self.run_cli(
                str(manifest),
                "--intent-file",
                str(intent),
                "--source-root",
                str(root / "source"),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run-valid", result.stdout)

    def test_initialize_falls_back_when_git_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.txt").write_text("v1\n", encoding="utf-8")
            intent = root / "intent.md"
            intent.write_text("Define quiet hours.\n", encoding="utf-8")
            manifest = source / ".planning" / "spec" / "quiet-hours" / "_run.json"
            environment = os.environ.copy()
            environment["PATH"] = ""
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(manifest),
                    "--initialize",
                    "--slug",
                    "quiet-hours",
                    "--mode",
                    "quick",
                    "--intent-file",
                    str(intent),
                    "--source-root",
                    str(source),
                ],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            data = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["source_identity"]["kind"], "directory")

    def test_intent_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, intent = self.initialize(root)
            intent.write_text("A different feature.\n", encoding="utf-8")
            result = self.run_cli(str(manifest), "--intent-file", str(intent))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("original intent", result.stderr)

    def test_source_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, intent = self.initialize(root)
            (root / "source" / "app.txt").write_text("v2\n", encoding="utf-8")
            result = self.run_cli(
                str(manifest),
                "--intent-file",
                str(intent),
                "--source-root",
                str(root / "source"),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source drift detected", result.stderr)

    def test_declared_output_does_not_invalidate_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.txt").write_text("v1\n", encoding="utf-8")
            intent = root / "intent.md"
            intent.write_text("Define quiet hours.\n", encoding="utf-8")
            output = source / "specs" / "quiet-hours" / "SPEC.md"
            manifest = source / ".planning" / "spec" / "quiet-hours" / "_run.json"

            initialized = self.run_cli(
                str(manifest),
                "--initialize",
                "--slug",
                "quiet-hours",
                "--mode",
                "quick",
                "--intent-file",
                str(intent),
                "--source-root",
                str(source),
                "--exclude",
                str(output),
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            output.parent.mkdir(parents=True)
            output.write_text("# Quiet hours\n", encoding="utf-8")
            resumed = self.run_cli(
                str(manifest),
                "--intent-file",
                str(intent),
                "--source-root",
                str(source),
            )

        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertIn("run-valid", resumed.stdout)

    def test_unsupported_analysis_version_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.initialize(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["analysis_version"] = "spec-run/v2"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(manifest))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported analysis_version", result.stderr)

    def test_schema_version_requires_an_integer(self) -> None:
        for invalid in (True, 1.0):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest, _ = self.initialize(root)
                data = json.loads(manifest.read_text(encoding="utf-8"))
                data["schema_version"] = invalid
                manifest.write_text(json.dumps(data), encoding="utf-8")
                result = self.run_cli(str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported schema_version", result.stderr)

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.initialize(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["trusted"] = True
            manifest.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(manifest))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported fields", result.stderr)

    def test_schema_is_valid_json(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "schemas" / "run-v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["properties"]["analysis_version"]["const"], "spec-run/v1")

    def test_skill_invokes_versioned_run_validator(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("scripts/validate_run.py", skill)
        self.assertIn('spec-run/v1', skill)
        self.assertIn('--exclude "<final-SPEC-path>"', skill)


if __name__ == "__main__":
    unittest.main()
