from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "validate_queue.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ValidateQueueCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_v2_with_source_and_analysis_metadata(self) -> None:
        result = self.run_cli(
            str(FIXTURES / "valid-v2.json"),
            "--spec",
            str(FIXTURES / "spec.md"),
            "--analysis",
            str(FIXTURES / "analysis.md"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VALID queue-v2", result.stdout)
        self.assertIn("digest=matched", result.stdout)
        self.assertIn("analysis=matched", result.stdout)

    def test_priority_one_must_sort_before_priority_two(self) -> None:
        result = self.run_cli(str(FIXTURES / "invalid-unsorted-v2.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("priority ASC, id ASC", result.stderr)

    def test_priority_outside_one_to_three_is_rejected(self) -> None:
        result = self.run_cli(str(FIXTURES / "invalid-priority-v2.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integer 1..3", result.stderr)

    def test_legacy_v1_is_fail_closed_by_default(self) -> None:
        result = self.run_cli(str(FIXTURES / "legacy-v1.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("read-only and not resumable", result.stderr)

    def test_legacy_v1_can_be_inspected_but_not_resumed(self) -> None:
        result = self.run_cli(
            str(FIXTURES / "legacy-v1.json"),
            "--allow-legacy-read",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("read-only; not resumable", result.stdout)

    def test_wrong_spec_digest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            other_spec = Path(tmp) / "other.md"
            other_spec.write_text("different spec\n", encoding="utf-8")
            result = self.run_cli(
                str(FIXTURES / "valid-v2.json"),
                "--spec",
                str(other_spec),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("spec digest mismatch", result.stderr)

    def test_analysis_body_is_bound_by_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "analysis.md"
            original = (FIXTURES / "analysis.md").read_text(encoding="utf-8")
            changed.write_text(original + "\nChanged body with unchanged metadata.\n", encoding="utf-8")
            result = self.run_cli(
                str(FIXTURES / "valid-v2.json"),
                "--analysis",
                str(changed),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("analysis digest mismatch", result.stderr)

    def test_resume_accepts_bound_declared_ids(self) -> None:
        result = self.run_cli(
            str(FIXTURES / "valid-v2.json"),
            "--resume",
            "--spec",
            str(FIXTURES / "spec.md"),
            "--analysis",
            str(FIXTURES / "analysis.md"),
            "--artifacts-dir",
            str(FIXTURES),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("analysis=matched", result.stdout)

    def test_undeclared_transition_reference_is_rejected(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["pending"][0]["transitions_targeted"] = ["T99"]
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(
                str(queue), "--analysis", str(FIXTURES / "analysis.md")
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("undeclared analysis ids: T99", result.stderr)

    def test_undeclared_invariant_reference_is_rejected(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["pending"][0]["invariants_targeted"] = ["I99"]
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(
                str(queue), "--analysis", str(FIXTURES / "analysis.md")
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("undeclared analysis ids: I99", result.stderr)

    def test_declared_id_format_is_canonical(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        original = (FIXTURES / "analysis.md").read_text(encoding="utf-8")
        changed = original.replace(
            "Declared transition IDs: T01", "Declared transition IDs: T01,T02"
        )
        data["analysis_sha256"] = hashlib.sha256(changed.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            analysis = directory / "analysis.md"
            queue.write_text(json.dumps(data), encoding="utf-8")
            analysis.write_text(changed, encoding="utf-8")
            result = self.run_cli(str(queue), "--analysis", str(analysis))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("canonical comma-space separators", result.stderr)

    def test_spec_digest_is_stable_across_line_endings(self) -> None:
        source = (FIXTURES / "spec.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            crlf_spec = Path(tmp) / "spec.md"
            crlf_spec.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
            result = self.run_cli(
                str(FIXTURES / "valid-v2.json"),
                "--spec",
                str(crlf_spec),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("digest=matched", result.stdout)

    def test_print_spec_digest_uses_same_normalization(self) -> None:
        source = (FIXTURES / "spec.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            crlf_spec = Path(tmp) / "spec.md"
            crlf_spec.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
            result = self.run_cli("--print-spec-sha256", str(crlf_spec))
        queue = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), queue["spec_sha256"])

    def test_duplicate_ids_across_buckets_are_rejected(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        duplicate = dict(data["pending"][0])
        duplicate["slug"] = "duplicate-id"
        data["done"] = [duplicate]
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate of", result.stderr)

    def test_attacks_only_rejects_golden_scenarios(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["mode"] = "attacks-only"
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("golden is forbidden", result.stderr)

    def test_targeted_mode_requires_focus(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["mode"] = "targeted"
        data["scenario_cap"] = 8
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("targeted mode requires a focus", result.stderr)

    def test_inventory_exhausted_state_rejects_pending_work(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["status"] = "complete"
        data["stop_reason"] = "scenario inventory exhausted"
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complete state requires empty pending/in_progress", result.stderr)

    def test_schema_version_must_be_integer(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["schema_version"] = 2.0
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only version 2", result.stderr)

    def test_standard_requires_thirty_percent_negative_paths(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        for scenario in data["pending"]:
            scenario["category"] = "golden"
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 30%", result.stderr)

    def test_mode_cap_completion_requires_actual_cap_and_empty_work(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["pending"] = data["pending"][:4]
        data["status"] = "complete"
        data["stop_reason"] = "mode scenario cap reached"
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mode cap completion requires exactly", result.stderr)

    def test_focus_completion_is_targeted_only(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        failed = []
        for scenario in data["pending"]:
            scenario["last_error"] = "fixture failure"
            failed.append(scenario)
        data["pending"] = []
        data["failed"] = failed
        data["status"] = "complete"
        data["stop_reason"] = "focus inventory exhausted"
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("valid only in targeted mode", result.stderr)

    def test_active_queue_requires_pending_or_in_progress(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        failed = []
        for scenario in data["pending"]:
            scenario["last_error"] = "fixture failure"
            failed.append(scenario)
        data["pending"] = []
        data["failed"] = failed
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("active state requires", result.stderr)

    def test_done_artifact_is_bound_to_path_digest_and_sentinel(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        scenario["attempts"] = 1
        body = "# A01 - Concurrent payment\n\n<!-- simulate-complete:A01 -->\n"
        scenario["artifact_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        data["done"] = [scenario]
        data["next_counter"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            artifact = directory / scenario["artifact_path"]
            queue.write_text(json.dumps(data), encoding="utf-8")
            with artifact.open("w", encoding="utf-8", newline="") as handle:
                handle.write(body)
            result = self.run_cli(
                str(queue),
                "--artifacts-dir",
                str(directory),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact.write_text("# tampered\n", encoding="utf-8")
            tampered = self.run_cli(
                str(queue),
                "--artifacts-dir",
                str(directory),
            )
        self.assertNotEqual(tampered.returncode, 0)
        self.assertIn("completion sentinel", tampered.stderr)
        self.assertIn("artifact digest mismatch", tampered.stderr)

    def test_done_artifact_requires_exact_header(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        body = "\n# A01 - Concurrent payment\n\n<!-- simulate-complete:A01 -->\n"
        scenario["artifact_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        data["done"] = [scenario]
        data["next_counter"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            artifact = directory / scenario["artifact_path"]
            queue.write_text(json.dumps(data), encoding="utf-8")
            artifact.write_text(body, encoding="utf-8")
            result = self.run_cli(str(queue), "--artifacts-dir", str(directory))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("header must be exactly", result.stderr)

    def test_done_artifact_rejects_undeclared_model_ids(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        body = (
            "# A01 - Concurrent payment\n\n"
            "Transitions targeted: [T99]\n\n"
            "<!-- simulate-complete:A01 -->\n"
        )
        scenario["artifact_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        data["done"] = [scenario]
        data["next_counter"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            artifact = directory / scenario["artifact_path"]
            queue.write_text(json.dumps(data), encoding="utf-8")
            artifact.write_text(body, encoding="utf-8")
            result = self.run_cli(
                str(queue),
                "--analysis",
                str(FIXTURES / "analysis.md"),
                "--artifacts-dir",
                str(directory),
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references undeclared transition ids: T99", result.stderr)

    def test_done_artifact_filename_suffix_matches_slug(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["artifact_path"] = "sim-001-wrong-slug.md"
        scenario["artifact_sha256"] = "0" * 64
        data["done"] = [scenario]
        data["next_counter"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("filename suffix must match scenario slug", result.stderr)

    def test_next_counter_is_strictly_above_reserved_prefixes(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["artifact_path"] = "sim-007-concurrent-payment.md"
        data["in_progress"] = [scenario]
        data["next_counter"] = 7
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("strictly greater than every reserved artifact prefix", result.stderr)

    def test_unbound_final_and_temporary_artifacts_are_preserved_and_reported(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["next_counter"] = 20
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            final = directory / "sim-009-orphan.md"
            temporary = directory / "sim-010-partial.md.tmp"
            queue.write_text(json.dumps(data), encoding="utf-8")
            final.write_text("orphan\n", encoding="utf-8")
            temporary.write_text("partial\n", encoding="utf-8")
            result = self.run_cli(str(queue), "--artifacts-dir", str(directory))
            self.assertTrue(final.exists())
            self.assertTrue(temporary.exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unbound final artifact", result.stderr)
        self.assertIn("unbound temporary artifact", result.stderr)
        self.assertIn("preserve it for reconciliation", result.stderr)

    def test_on_disk_prefix_constrains_next_counter(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["next_counter"] = 10
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            final = directory / "sim-010-orphan.md"
            queue.write_text(json.dumps(data), encoding="utf-8")
            final.write_text("orphan\n", encoding="utf-8")
            result = self.run_cli(str(queue), "--artifacts-dir", str(directory))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("strictly greater than every on-disk scenario prefix", result.stderr)

    def test_bound_temporary_artifact_requires_reconciliation(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        data["in_progress"] = [scenario]
        data["next_counter"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            temporary = directory / "sim-001-concurrent-payment.md.tmp"
            queue.write_text(json.dumps(data), encoding="utf-8")
            temporary.write_text("partial\n", encoding="utf-8")
            result = self.run_cli(str(queue), "--artifacts-dir", str(directory))
            self.assertTrue(temporary.exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is bound to in_progress A01", result.stderr)

    def test_in_progress_final_is_preserved_for_promotion_reconciliation(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        data["in_progress"] = [scenario]
        data["next_counter"] = 2
        body = "# A01 - Concurrent payment\n\n<!-- simulate-complete:A01 -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            queue = directory / "queue.json"
            artifact = directory / scenario["artifact_path"]
            queue.write_text(json.dumps(data), encoding="utf-8")
            artifact.write_text(body, encoding="utf-8")
            result = self.run_cli(
                str(queue),
                "--resume",
                "--spec",
                str(FIXTURES / "spec.md"),
                "--analysis",
                str(FIXTURES / "analysis.md"),
                "--artifacts-dir",
                str(directory),
            )
            self.assertTrue(artifact.exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("in_progress has final artifact", result.stderr)
        self.assertIn("preserve it and reconcile", result.stderr)

    def test_attempt_bucket_contract(self) -> None:
        base = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        cases = []

        pending = json.loads(json.dumps(base))
        pending["pending"][0]["attempts"] = 1
        cases.append((pending, "pending scenarios require 0"))

        in_progress = json.loads(json.dumps(base))
        scenario = in_progress["pending"].pop(0)
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        in_progress["in_progress"] = [scenario]
        in_progress["next_counter"] = 2
        cases.append((in_progress, "in_progress scenarios require at least 1"))

        done = json.loads(json.dumps(base))
        scenario = done["pending"].pop(0)
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        scenario["artifact_sha256"] = "0" * 64
        done["done"] = [scenario]
        done["next_counter"] = 2
        cases.append((done, "done scenarios require at least 1"))

        failed = json.loads(json.dumps(base))
        scenario = failed["pending"].pop(0)
        scenario["artifact_path"] = "sim-001-concurrent-payment.md"
        scenario["last_error"] = "fixture failure"
        failed["failed"] = [scenario]
        failed["next_counter"] = 2
        cases.append((failed, "failed scenarios require at least 1"))

        for data, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                queue = Path(tmp) / "queue.json"
                queue.write_text(json.dumps(data), encoding="utf-8")
                result = self.run_cli(str(queue))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)

    def test_failed_reservation_is_valid_and_constrains_counter(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        scenario = data["pending"].pop(0)
        scenario["attempts"] = 1
        scenario["last_error"] = "worker interrupted"
        scenario["artifact_path"] = "sim-015-concurrent-payment.md"
        data["failed"] = [scenario]
        data["next_counter"] = 16
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            valid = self.run_cli(str(queue))
            data["next_counter"] = 15
            queue.write_text(json.dumps(data), encoding="utf-8")
            invalid = self.run_cli(str(queue))
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("strictly greater than every reserved artifact prefix", invalid.stderr)

    def test_resume_requires_all_integrity_inputs(self) -> None:
        result = self.run_cli(str(FIXTURES / "valid-v2.json"), "--resume")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--resume requires", result.stderr)

    def test_mode_cap_is_exact_and_bounded(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["mode"] = "deep"
        data["scenario_cap"] = 21
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("deep mode requires 20", result.stderr)

    def test_unknown_fields_fail_closed(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["invented_protocol_flag"] = True
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported keys", result.stderr)

    def test_wrong_json_types_report_errors_instead_of_crashing(self) -> None:
        data = json.loads((FIXTURES / "valid-v2.json").read_text(encoding="utf-8"))
        data["mode"] = ["standard"]
        data["pending"][0]["category"] = ["attack"]
        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue.json"
            queue.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli(str(queue))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("unsupported mode", result.stderr)
        self.assertIn("expected golden, edge, or attack", result.stderr)

    def test_schema_document_is_valid_json(self) -> None:
        schema = json.loads((SKILL_DIR / "schemas" / "queue-v2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 2)


if __name__ == "__main__":
    unittest.main()
