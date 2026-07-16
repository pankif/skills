from __future__ import annotations

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_spec.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

module_spec = importlib.util.spec_from_file_location("validate_spec", VALIDATOR_PATH)
assert module_spec and module_spec.loader
validate_spec = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(validate_spec)


class ValidateSpecTests(unittest.TestCase):
    def test_valid_fixture_is_syntax_valid(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        self.assertEqual(validate_spec.validate_text(text), [])

    def test_missing_appendix_is_rejected(self) -> None:
        text = (FIXTURES / "missing-appendix.md").read_text(encoding="utf-8")
        errors = validate_spec.validate_text(text)
        self.assertTrue(any("Technical appendix" in error for error in errors), errors)

    def test_reordered_sections_are_rejected(self) -> None:
        text = (FIXTURES / "reordered.md").read_text(encoding="utf-8")
        errors = validate_spec.validate_text(text)
        self.assertIn("headings: required ## sections are out of order", errors)

    def test_duplicate_section_is_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("## Glossary", "## Purpose\nDuplicate.\n\n## Glossary", 1)
        errors = validate_spec.validate_text(text)
        self.assertTrue(any("exactly one '## Purpose'" in error for error in errors), errors)

    def test_invalid_frontmatter_date_is_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("last_updated: 2026-07-17", "last_updated: 2026-02-30", 1)
        errors = validate_spec.validate_text(text)
        self.assertIn("frontmatter: 'last_updated' must be a real calendar date", errors)

    def test_unsupported_frontmatter_scalar_is_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("domain: notifications", "domain: [notifications]", 1)
        errors = validate_spec.validate_text(text)
        self.assertIn("line 3: unsupported frontmatter scalar for 'domain'", errors)

    def test_h1_must_match_decoded_frontmatter_title(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("# Shared quiet hours", "# Personal quiet hours", 1)
        errors = validate_spec.validate_text(text)
        self.assertIn("body: H1 title must exactly match frontmatter 'title'", errors)

    def test_missing_appendix_warning_is_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace(
            "> Derived from repository evidence; this section is implementation guidance, not the product contract.",
            "Derived from repository evidence.",
            1,
        )
        errors = validate_spec.validate_text(text)
        self.assertIn("boundary: technical appendix must begin with a blockquote warning", errors)

    def test_missing_required_appendix_section_is_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("### Integration points\nUnknown.\n\n", "", 1)
        errors = validate_spec.validate_text(text)
        self.assertTrue(
            any("exactly one '### Integration points'" in error for error in errors), errors
        )

    def test_reordered_appendix_sections_are_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("### Evidence and conflicts", "### TEMP", 1)
        text = text.replace("### Stack & placement", "### Evidence and conflicts", 1)
        text = text.replace("### TEMP", "### Stack & placement", 1)
        errors = validate_spec.validate_text(text)
        self.assertIn("headings: required ### sections are out of order", errors)

    def test_duplicate_appendix_section_is_rejected(self) -> None:
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace(
            "### Stack & placement",
            "### Evidence and conflicts\nDuplicate.\n\n### Stack & placement",
            1,
        )
        errors = validate_spec.validate_text(text)
        self.assertTrue(
            any("exactly one '### Evidence and conflicts'" in error for error in errors),
            errors,
        )

    def test_validator_does_not_claim_semantic_validation(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = validate_spec.main([str(FIXTURES / "valid.md")])
        self.assertEqual(exit_code, 0)
        self.assertIn("syntax-validated", output.getvalue())
        self.assertIn("structure only", output.getvalue())
        self.assertIn("semantic correctness", output.getvalue())


if __name__ == "__main__":
    unittest.main()
