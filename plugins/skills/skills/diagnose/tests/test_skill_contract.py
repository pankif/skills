from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_validator_invocations_are_skill_relative_and_portable(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("python scripts/validate_case.py", skill)
        self.assertGreaterEqual(
            skill.count('"<diagnose-skill-dir>/scripts/validate_case.py"'),
            2,
        )
        for launcher in ("python3", "python", "py -3"):
            self.assertIn(launcher, skill)

    def test_independent_falsifier_is_a_confirmation_gate(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("same-agent challenge", skill)
        self.assertIn("can never authorize `CAUSE-CONFIRMED`", skill)

    def test_quick_mode_never_claims_proven_cause(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`quick` may report only a **best-supported explanation**", skill)
        self.assertIn("escalate to `strict`", skill)

    def test_case_paths_are_quoted_and_missing_python_caps_terminal(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"<out>/CASE.jsonl"', skill)
        self.assertIn('"<candidate>" --previous "<snapshot>"', skill)
        self.assertIn("Missing mandatory CASE validation caps the terminal", skill)

    def test_eval_catalog_is_versioned_and_covers_review_cases(self) -> None:
        catalog = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 1)
        self.assertGreaterEqual(catalog["evaluation_version"], 1)
        names = {case["name"] for case in catalog["evals"]}
        self.assertIn("strict-independent-falsifier-unavailable", names)
        self.assertIn("unsupported-analysis-version-resume", names)
        self.assertIn("incident-capability-fallback", names)

    def test_schema_requires_supported_analysis_version(self) -> None:
        schema = json.loads((SKILL_ROOT / "schemas" / "case-v1.schema.json").read_text(encoding="utf-8"))
        header = schema["$defs"]["header"]
        self.assertIn("analysis_version", header["required"])
        self.assertEqual(header["properties"]["analysis_version"]["const"], 1)


if __name__ == "__main__":
    unittest.main()
