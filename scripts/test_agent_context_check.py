from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("agent_context_check.py")
CONTEXT_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "justfile",
    "docs/development/README.md",
    "docs/development/architecture.md",
    "docs/development/windows.md",
    "docs/development/templates/high-risk-change.md",
    "docs/development/templates/fresh-review.md",
    "docs/development/templates/windows-validation.md",
    "src/platform/AGENTS.md",
    "src/protocol/AGENTS.md",
    "src/persist/AGENTS.md",
    "src/detect/AGENTS.md",
)
REACHABLE_CONTEXT_FILES = tuple(
    relative
    for relative in CONTEXT_FILES
    if relative.endswith(".md") and relative not in {"AGENTS.md", "CLAUDE.md"}
)
TEMPLATE_FIELDS = {
    "docs/development/templates/high-risk-change.md": (
        "observable-behavior",
        "scope-boundary",
        "protected-invariants",
        "compatibility-risk",
        "evidence-plan",
        "rollback-and-residual-risk",
        "open-decisions",
    ),
    "docs/development/templates/fresh-review.md": (
        "review-requirement",
        "review-rules",
        "review-diff",
        "review-evidence",
        "review-exclusions",
        "review-output-contract",
    ),
    "docs/development/templates/windows-validation.md": (
        "windows-build",
        "windows-environment",
        "windows-artifact",
        "windows-conpty-source",
        "windows-results",
        "windows-evidence",
        "windows-unverified-risk",
    ),
}
WINDOWS_EVIDENCE_MARKERS = (
    "<!-- agent-evidence: windows-enhanced-input-probe "
    "command=scripts/windows_conpty_enhanced_input_probe.ps1 "
    "argv=-ExePath,-ExpectedConsoleHostPath "
    "claims=server-conpty-input,app-local-openconsole "
    "conditional-claim=app-local-openconsole:-ExpectedConsoleHostPath "
    "gaps=win32-input-capture,client-private-wire -->",
    "<!-- agent-evidence: windows-arm64-installer "
    "workflow=.github/workflows/windows-arm64.yml "
    "artifact=published-preview "
    "gaps=current-candidate-package,native-arm64-binary -->",
)


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_valid_context(root: Path) -> None:
    for relative in CONTEXT_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    root_links = "".join(f"[{relative}]({relative})\n" for relative in REACHABLE_CONTEXT_FILES)
    (root / "AGENTS.md").write_text(f"# Root\n\n{root_links}", encoding="utf-8")
    for relative, fields in TEMPLATE_FIELDS.items():
        markers = "".join(f"<!-- agent-field: {field} -->\n" for field in fields)
        (root / relative).write_text(f"# Template\n\n{markers}", encoding="utf-8")
    (root / "docs/development/windows.md").write_text(
        "# Windows\n\n" + "\n".join(WINDOWS_EVIDENCE_MARKERS) + "\n",
        encoding="utf-8",
    )
    for relative in (
        "scripts/windows_conpty_enhanced_input_probe.ps1",
        ".github/workflows/windows-arm64.yml",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# evidence source\n", encoding="utf-8")


class AgentContextCheckTests(unittest.TestCase):
    def test_missing_required_instruction_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_checker(Path(tmp))

        self.assertEqual(result.returncode, 1)
        self.assertIn("src/platform/AGENTS.md: required agent context file is missing", result.stderr)

    def test_complete_context_inventory_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "agent context check passed\n")

    def test_broken_relative_markdown_link_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "docs/development/README.md").write_text(
                "# Development\n\n[missing](missing.md)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: broken relative link: missing.md",
            result.stderr,
        )

    def test_unknown_documented_just_recipe_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "docs/development/README.md").write_text(
                "# Development\n\nRun `just missing-check`.\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: unknown just recipe: missing-check",
            result.stderr,
        )

    def test_missing_template_field_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/templates/high-risk-change.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "<!-- agent-field: protected-invariants -->\n",
                    "",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/templates/high-risk-change.md: missing template field: protected-invariants",
            result.stderr,
        )

    def test_claude_import_must_target_root_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "CLAUDE.md").unlink()
            (root / "CLAUDE.md").write_text("# copied instructions\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "CLAUDE.md: must be a regular file containing exactly @AGENTS.md",
            result.stderr,
        )

    def test_claude_import_is_cross_platform_context_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_relative_link_must_stay_inside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "docs/development/README.md").write_text(
                "# Development\n\n[outside](../../../outside.md)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: relative link escapes repository: ../../../outside.md",
            result.stderr,
        )

    def test_markdown_link_examples_in_fenced_code_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "docs/development/README.md").write_text(
                "# Development\n\n```markdown\n[placeholder](missing.md)\n```\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_four_space_indented_fence_opener_does_not_hide_real_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "    ```\n[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backtick_in_info_string_does_not_open_backtick_fence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "``` bad`info\n"
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_four_space_indented_fence_closer_does_not_expose_code_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "```\n    ```\n"
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)\n```",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_uninventoried_local_instructions_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "src/server/AGENTS.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Server\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/server/AGENTS.md: local instructions are not in the agent context inventory",
            result.stderr,
        )

    def test_relative_link_path_case_must_match_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "docs/development/README.md").write_text(
                "# Development\n\n[runner](../../Justfile)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: relative link has incorrect path case: ../../Justfile",
            result.stderr,
        )

    def test_duplicate_template_field_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/templates/high-risk-change.md"
            with path.open("a", encoding="utf-8") as fh:
                fh.write("<!-- agent-field: observable-behavior -->\n")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/templates/high-risk-change.md: duplicate template field: observable-behavior",
            result.stderr,
        )

    def test_enhanced_input_probe_requires_executable_path_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "argv=-ExePath,-ExpectedConsoleHostPath",
                    "argv=-ExpectedConsoleHostPath",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: windows-enhanced-input-probe evidence contract mismatch: argv",
            result.stderr,
        )

    def test_enhanced_input_probe_keeps_client_capture_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "gaps=win32-input-capture,client-private-wire",
                    "gaps=win32-input-capture",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: windows-enhanced-input-probe evidence contract mismatch: gaps",
            result.stderr,
        )

    def test_openconsole_claim_stays_conditional_on_expected_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "conditional-claim=app-local-openconsole:-ExpectedConsoleHostPath",
                    "conditional-claim=app-local-openconsole:always",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: windows-enhanced-input-probe evidence contract mismatch: conditional-claim",
            result.stderr,
        )

    def test_arm64_contract_does_not_claim_current_candidate_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "artifact=published-preview",
                    "artifact=current-candidate-package",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: windows-arm64-installer evidence contract mismatch: artifact",
            result.stderr,
        )

    def test_windows_evidence_source_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "scripts/windows_conpty_enhanced_input_probe.ps1").unlink()
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: evidence source is missing: scripts/windows_conpty_enhanced_input_probe.ps1",
            result.stderr,
        )

    def test_context_file_must_be_reachable_from_root_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)\n",
                    "",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_documented_just_recipe_is_resolved_from_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "justfile").write_text("check:\n    @true\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text("# Development\n\nRun `just check`.\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_policy_wildcard_is_not_treated_as_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            readme = root / "docs/development/README.md"
            readme.write_text("# Development\n\nDo not run `just release*`.\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_repository_path_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            readme = root / "docs/development/README.md"
            readme.write_text("# Development\n\nSee `src/missing.rs`.\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: repository path reference is missing: src/missing.rs",
            result.stderr,
        )

    def test_repository_path_symbols_globs_and_declared_exceptions_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            for relative in ("src/main.rs", "src/detect/manifests/codex.toml"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n"
                "`src/main.rs::main`\n"
                "`src/detect/manifests/*.toml`\n"
                "`src/platform/<os>.rs`\n"
                "`website/src/content/docs/`\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_windows_evidence_contract_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    WINDOWS_EVIDENCE_MARKERS[1] + "\n",
                    "",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: missing evidence contract: windows-arm64-installer",
            result.stderr,
        )

    def test_duplicate_windows_evidence_contract_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(WINDOWS_EVIDENCE_MARKERS[1] + "\n")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: duplicate evidence contract: windows-arm64-installer",
            result.stderr,
        )

    def test_inline_code_does_not_make_context_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "`[src/platform/AGENTS.md](src/platform/AGENTS.md)`",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_escaped_backticks_do_not_hide_a_real_context_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    r"\`[src/platform/AGENTS.md](src/platform/AGENTS.md)\`",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backslash_does_not_escape_a_closing_code_span_delimiter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    r"`prefix \`[src/platform/AGENTS.md](src/platform/AGENTS.md)`",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_image_does_not_make_context_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "![src/platform/AGENTS.md](src/platform/AGENTS.md)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_linked_image_target_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n[![badge](missing.png)](architecture.md)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: broken relative link: missing.png",
            result.stderr,
        )

    def test_nested_link_is_checked_instead_of_invalid_outer_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n"
                "[outer [inner](missing.md)](architecture.md)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: broken relative link: missing.md",
            result.stderr,
        )

    def test_reference_style_context_link_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "[src/platform/AGENTS.md][platform-context]\n\n"
                    "[platform-context]: src/platform/AGENTS.md",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_inline_link_destination_supports_balanced_parentheses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            topic = root / "docs/development/topic_(v1).md"
            topic.write_text("# Topic\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n[topic](topic_(v1).md)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_angle_link_destination_preserves_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            topic = root / "docs/development/topic v1.md"
            topic.write_text("# Topic\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n[topic](<topic v1.md>)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_percent_encoded_hash_remains_part_of_link_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            topic = root / "docs/development/topic#v1.md"
            topic.write_text("# Topic\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n[topic](topic%23v1.md)\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_first_reference_definition_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "[src/platform/AGENTS.md][platform-context]\n\n"
                    "[platform-context]: src/platform/AGENTS.md\n"
                    "[platform-context]: missing.md",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shortcut_reference_context_link_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "[platform-context]\n\n"
                    "[platform-context]: src/platform/AGENTS.md",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_escaped_image_marker_keeps_normal_link_reachability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    r"\![src/platform/AGENTS.md](src/platform/AGENTS.md)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_escaped_link_opener_does_not_make_context_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    r"\[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_even_backslashes_keep_link_opener_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    r"\\[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_inline_link_tail_does_not_make_context_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md garbage)",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_malformed_reference_tail_does_not_make_context_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "AGENTS.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "[src/platform/AGENTS.md](src/platform/AGENTS.md)",
                    "[src/platform/AGENTS.md][platform-context]\n\n"
                    "[platform-context]: src/platform/AGENTS.md garbage",
                ),
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "src/platform/AGENTS.md: agent context file is not reachable from AGENTS.md",
            result.stderr,
        )

    def test_glob_repository_path_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            root = outer / "repo"
            root.mkdir()
            write_valid_context(root)
            (outer / "outside-fixture").write_text("secret\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n`src/../../outside-*`\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: repository path reference escapes repository: src/../../outside-*",
            result.stderr,
        )

    def test_repository_path_cannot_follow_symlink_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            root = outer / "repo"
            root.mkdir()
            write_valid_context(root)
            outside = outer / "outside"
            outside.mkdir()
            (outside / "secret.rs").write_text("secret\n", encoding="utf-8")
            try:
                (root / "src/external").symlink_to(outside, target_is_directory=True)
            except OSError as error:
                if os.name == "nt" and getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privilege is unavailable")
                raise
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n`src/external/secret.rs`\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: repository path reference escapes repository: src/external/secret.rs",
            result.stderr,
        )

    def test_glob_repository_path_case_must_match_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            manifest = root / "src/detect/manifests/codex.toml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("id = \"codex\"\n", encoding="utf-8")
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\n`src/Detect/manifests/*.toml`\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: repository path reference has incorrect path case: src/Detect/manifests/*.toml",
            result.stderr,
        )

    def test_evidence_contract_in_fenced_code_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/windows.md"
            path.write_text(
                "# Windows\n\n```markdown\n"
                + "\n".join(WINDOWS_EVIDENCE_MARKERS)
                + "\n```\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/windows.md: missing evidence contract: windows-arm64-installer",
            result.stderr,
        )

    def test_evidence_contract_rejects_duplicate_unknown_and_malformed_attributes(self) -> None:
        mutations = {
            "duplicate": (
                "artifact=published-preview",
                "artifact=current-candidate-package artifact=published-preview",
            ),
            "unknown": (
                "artifact=published-preview",
                "artifact=published-preview extra=value",
            ),
            "malformed": (
                "artifact=published-preview",
                "artifact=published-preview stray-token",
            ),
        }
        for name, (old, new) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_valid_context(root)
                path = root / "docs/development/windows.md"
                path.write_text(
                    path.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )
                result = run_checker(root)

                self.assertEqual(result.returncode, 1)
                self.assertIn(
                    "docs/development/windows.md: windows-arm64-installer evidence contract has invalid attributes",
                    result.stderr,
                )

    def test_just_setting_is_not_treated_as_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "justfile").write_text(
                'set shell := ["sh", "-cu"]\n',
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text("# Development\n\nRun `just set`.\n", encoding="utf-8")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: unknown just recipe: set",
            result.stderr,
        )

    def test_just_alias_and_underscore_recipe_are_callable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "justfile").write_text(
                "real-check:\n    @true\n"
                "alias check := real-check\n"
                "_internal-check:\n    @true\n",
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\nRun `just check` and `just _internal-check`.\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_quiet_just_recipe_is_callable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "justfile").write_text(
                "@quiet-check:\n    @true\n",
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\nRun `just quiet-check`.\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_just_function_is_not_treated_as_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "justfile").write_text(
                'url() := "https://example.com"\n',
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(
                "# Development\n\nRun `just url`.\n",
                encoding="utf-8",
            )
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "docs/development/README.md: unknown just recipe: url",
            result.stderr,
        )

    def test_required_context_directory_reports_stable_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            path = root / "docs/development/architecture.md"
            path.unlink()
            path.mkdir()
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(
            "docs/development/architecture.md: required agent context path is not a regular file",
            result.stderr,
        )

    def test_invalid_utf8_context_reports_stable_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_context(root)
            (root / "docs/development/architecture.md").write_bytes(b"\xff\xfe")
            result = run_checker(root)

        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(
            "docs/development/architecture.md: required agent context file is not valid UTF-8",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
