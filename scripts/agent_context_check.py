#!/usr/bin/env python3
"""Validate the repository's agent-facing context structure."""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CONTEXT_FILES = (
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
LOCAL_INSTRUCTION_FILES = {
    relative
    for relative in REQUIRED_CONTEXT_FILES
    if relative.startswith("src/") and relative.endswith("/AGENTS.md")
}
REACHABLE_CONTEXT_FILES = {
    relative
    for relative in REQUIRED_CONTEXT_FILES
    if relative.endswith(".md") and relative != "CLAUDE.md"
}
CHECKED_MARKDOWN_FILES = tuple(sorted(REACHABLE_CONTEXT_FILES))
AGENT_FIELD_RE = re.compile(r"<!--\s*agent-field:\s*([a-z0-9-]+)\s*-->")
AGENT_EVIDENCE_RE = re.compile(
    r"<!--\s*agent-evidence:\s*([a-z0-9-]+)\s+([^>]*?)\s*-->"
)
FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
REFERENCE_DEFINITION_RE = re.compile(r"^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*(.+)$", re.MULTILINE)
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
WINDOWS_EVIDENCE_CONTRACTS = {
    "windows-enhanced-input-probe": {
        "command": "scripts/windows_conpty_enhanced_input_probe.ps1",
        "argv": "-ExePath,-ExpectedConsoleHostPath",
        "claims": "server-conpty-input,app-local-openconsole",
        "conditional-claim": "app-local-openconsole:-ExpectedConsoleHostPath",
        "gaps": "win32-input-capture,client-private-wire",
    },
    "windows-arm64-installer": {
        "workflow": ".github/workflows/windows-arm64.yml",
        "artifact": "published-preview",
        "gaps": "current-candidate-package,native-arm64-binary",
    },
}
REPOSITORY_PATH_PREFIXES = (
    ".agents/",
    ".github/",
    ".githooks/",
    "docs/",
    "packaging/",
    "scripts/",
    "skills/",
    "src/",
    "vendor/",
    "website/",
)
GENERATED_PATH_REFERENCES = {"website/src/content/docs/"}


@dataclass(frozen=True)
class PathLookup:
    status: str
    path: Path | None = None


@dataclass(frozen=True)
class MarkdownLink:
    target: str
    is_image: bool


def lookup_repository_path(root: Path, relative: Path) -> PathLookup:
    """Resolve a repository-relative path with deterministic case and escape checks."""
    root = Path(os.path.abspath(root))
    if relative.is_absolute() or ".." in relative.parts:
        return PathLookup("escape")

    normalized = Path(os.path.normpath(relative))
    if normalized == Path("."):
        normalized = Path()

    current = root
    case_mismatch = False
    for part in normalized.parts:
        if not current.is_dir():
            return PathLookup("missing")
        try:
            entries = list(current.iterdir())
        except OSError:
            return PathLookup("missing")
        exact = [entry for entry in entries if entry.name == part]
        if len(exact) == 1:
            current = exact[0]
            continue
        folded = [entry for entry in entries if entry.name.casefold() == part.casefold()]
        if len(folded) > 1:
            return PathLookup("ambiguous-case")
        if not folded:
            return PathLookup("missing")
        current = folded[0]
        case_mismatch = True

    if not current.exists():
        return PathLookup("missing")
    try:
        current.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return PathLookup("escape", current)
    return PathLookup("case-mismatch" if case_mismatch else "ok", current)


def path_exists_with_exact_case(root: Path, relative: Path) -> bool:
    return lookup_repository_path(root, relative).status == "ok"


def load_required_context_files(root: Path) -> tuple[dict[str, str], list[str]]:
    texts: dict[str, str] = {}
    errors: list[str] = []
    for relative in REQUIRED_CONTEXT_FILES:
        lookup = lookup_repository_path(root, Path(relative))
        if lookup.status in {"missing", "case-mismatch", "ambiguous-case"}:
            errors.append(f"{relative}: required agent context file is missing")
            continue
        if lookup.status == "escape":
            errors.append(f"{relative}: required agent context path escapes repository")
            continue
        path = lookup.path
        if path is None or not path.is_file():
            errors.append(f"{relative}: required agent context path is not a regular file")
            continue
        try:
            texts[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: required agent context file is not valid UTF-8")
        except OSError:
            errors.append(f"{relative}: required agent context file could not be read")
    return texts, errors


def check_claude_import(root: Path, texts: dict[str, str]) -> list[str]:
    alias = root / "CLAUDE.md"
    if (
        not alias.is_symlink()
        and alias.is_file()
        and texts.get("CLAUDE.md") == "@AGENTS.md\n"
    ):
        return []
    return ["CLAUDE.md: must be a regular file containing exactly @AGENTS.md"]


def check_local_instruction_inventory(root: Path) -> list[str]:
    source_root = root / "src"
    if not source_root.exists():
        return []
    errors: list[str] = []
    for path in sorted(source_root.rglob("AGENTS.md")):
        relative = path.relative_to(root).as_posix()
        if relative not in LOCAL_INSTRUCTION_FILES:
            errors.append(
                f"{relative}: local instructions are not in the agent context inventory"
            )
    return errors


def markdown_link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    index = 0
    while index < len(target):
        if target[index] == "\\":
            index += 2
            continue
        if target[index] in "#?":
            target = target[:index]
            break
        index += 1
    target = re.sub(r"\\(.)", r"\1", target)
    target = unquote(target)
    if not target or target.startswith("#"):
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    return target


def strip_fenced_code(text: str) -> str:
    output: list[str] = []
    closing_fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        match = FENCE_RE.match(line)
        if closing_fence is None and match:
            marker = match.group(1)
            if marker[0] == "`" and "`" in line[match.end() :]:
                output.append(line)
                continue
            closing_fence = (marker[0], len(marker))
            output.append("\n" if line.endswith("\n") else "")
            continue
        if closing_fence is not None:
            marker, minimum = closing_fence
            match = FENCE_RE.match(line)
            if (
                match is not None
                and match.group(1)[0] == marker
                and len(match.group(1)) >= minimum
                and not line[match.end() :].strip()
            ):
                closing_fence = None
            output.append("\n" if line.endswith("\n") else "")
            continue
        output.append(line)
    return "".join(output)


def is_backslash_escaped(text: str, index: int) -> bool:
    preceding_slashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        preceding_slashes += 1
        index -= 1
    return preceding_slashes % 2 == 1


def inline_code_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index] != "`" or is_backslash_escaped(text, index):
            index += 1
            continue
        opening_end = index
        while opening_end < len(text) and text[opening_end] == "`":
            opening_end += 1
        width = opening_end - index
        cursor = opening_end
        closing_end = None
        while cursor < len(text):
            if text[cursor] != "`":
                cursor += 1
                continue
            run_end = cursor
            while run_end < len(text) and text[run_end] == "`":
                run_end += 1
            if run_end - cursor == width:
                closing_end = run_end
                break
            cursor = run_end
        if closing_end is None:
            index = opening_end
            continue
        ranges.append((index, closing_end))
        index = closing_end
    return ranges


def strip_inline_code(text: str) -> str:
    output = list(text)
    for start, end in inline_code_ranges(text):
        for index in range(start, end):
            if output[index] != "\n":
                output[index] = " "
    return "".join(output)


def strip_markdown_code(text: str) -> str:
    return strip_inline_code(strip_fenced_code(text))


def inline_code_spans(text: str) -> list[str]:
    text = strip_fenced_code(text)
    spans: list[str] = []
    for start, end in inline_code_ranges(text):
        opening_end = start
        while opening_end < end and text[opening_end] == "`":
            opening_end += 1
        width = opening_end - start
        spans.append(text[opening_end : end - width])
    return spans


def find_closing_bracket(text: str, opening: int) -> int | None:
    depth = 1
    index = opening + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == "[":
            depth += 1
        elif text[index] == "]":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def parse_markdown_title(text: str, opening: int) -> int | None:
    delimiter = text[opening]
    closing_delimiter = ")" if delimiter == "(" else delimiter
    index = opening + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == closing_delimiter:
            return index + 1
        if delimiter == "(" and text[index] == "(":
            return None
        index += 1
    return None


def parse_inline_link_tail(text: str, index: int) -> int | None:
    if index < len(text) and text[index] == ")":
        return index
    if index >= len(text) or not text[index].isspace():
        return None
    while index < len(text) and text[index].isspace():
        index += 1
    if index < len(text) and text[index] == ")":
        return index
    if index >= len(text) or text[index] not in {'"', "'", "("}:
        return None
    title_end = parse_markdown_title(text, index)
    if title_end is None:
        return None
    index = title_end
    while index < len(text) and text[index].isspace():
        index += 1
    return index if index < len(text) and text[index] == ")" else None


def parse_inline_link_destination(text: str, opening: int) -> tuple[str, int] | None:
    index = opening + 1
    while index < len(text) and text[index] in " \t\n":
        index += 1
    if index >= len(text):
        return None

    if text[index] == "<":
        target_start = index + 1
        index = target_start
        while index < len(text):
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == ">":
                target = text[target_start:index]
                closing = parse_inline_link_tail(text, index + 1)
                return (target, closing) if closing is not None else None
            index += 1
        return None

    target_start = index
    depth = 0
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 2
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                return text[target_start:index], index
            depth -= 1
        elif character.isspace() and depth == 0:
            closing = parse_inline_link_tail(text, index)
            if closing is None:
                return None
            return text[target_start:index], closing
        index += 1
    return None


def reference_tail_is_valid(raw: str, index: int) -> bool:
    if index == len(raw):
        return True
    if not raw[index].isspace():
        return False
    while index < len(raw) and raw[index].isspace():
        index += 1
    if index == len(raw):
        return True
    if raw[index] not in {'"', "'", "("}:
        return False
    title_end = parse_markdown_title(raw, index)
    return title_end is not None and not raw[title_end:].strip()


def reference_destination(raw: str) -> str | None:
    raw = raw.lstrip()
    if not raw:
        return None
    if raw.startswith("<"):
        index = 1
        while index < len(raw):
            if raw[index] == "\\":
                index += 2
                continue
            if raw[index] == ">":
                return raw[1:index] if reference_tail_is_valid(raw, index + 1) else None
            index += 1
        return None

    depth = 0
    index = 0
    while index < len(raw):
        character = raw[index]
        if character == "\\":
            index += 2
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                return None
            depth -= 1
        elif character.isspace() and depth == 0:
            break
        index += 1
    target = raw[:index]
    if not target or depth != 0 or not reference_tail_is_valid(raw, index):
        return None
    return target


def normalize_reference_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def markdown_links(text: str) -> list[MarkdownLink]:
    visible = strip_markdown_code(text)
    definitions: dict[str, str] = {}
    definition_ranges: list[tuple[int, int]] = []
    for match in REFERENCE_DEFINITION_RE.finditer(visible):
        target = reference_destination(match.group(2))
        if target is not None:
            definitions.setdefault(normalize_reference_label(match.group(1)), target)
            definition_ranges.append(match.span())

    links: list[MarkdownLink] = []
    index = 0
    while index < len(visible):
        definition = next(
            (
                (start, end)
                for start, end in definition_ranges
                if start <= index < end
            ),
            None,
        )
        if definition is not None:
            index = definition[1]
            continue
        if visible[index] != "[":
            index += 1
            continue
        if is_backslash_escaped(visible, index):
            index += 1
            continue
        closing = find_closing_bracket(visible, index)
        if closing is None:
            index += 1
            continue
        is_image = (
            index > 0
            and visible[index - 1] == "!"
            and not is_backslash_escaped(visible, index - 1)
        )
        label = visible[index + 1 : closing]
        nested_links = markdown_links(label) if "[" in label else []
        links.extend(nested_links)
        has_nested_link = any(not link.is_image for link in nested_links)
        following = closing + 1
        if following < len(visible) and visible[following] == "(":
            parsed = parse_inline_link_destination(visible, following)
            if parsed is not None:
                target, end = parsed
                if not has_nested_link:
                    links.append(MarkdownLink(target=target, is_image=is_image))
                index = end + 1
                continue
        elif following < len(visible) and visible[following] == "[":
            reference_end = find_closing_bracket(visible, following)
            if reference_end is not None:
                reference = visible[following + 1 : reference_end] or label
                target = definitions.get(normalize_reference_label(reference))
                if target is not None and not has_nested_link:
                    links.append(MarkdownLink(target=target, is_image=is_image))
                index = reference_end + 1
                continue
        else:
            target = definitions.get(normalize_reference_label(label))
            if target is not None and not has_nested_link:
                links.append(MarkdownLink(target=target, is_image=is_image))
        index = closing + 1
    return links


def lexical_repository_relative(root: Path, candidate: Path) -> Path | None:
    lexical_root = Path(os.path.abspath(root))
    lexical_target = Path(os.path.normpath(candidate))
    try:
        return lexical_target.relative_to(lexical_root)
    except ValueError:
        return None


def check_relative_markdown_links(root: Path, texts: dict[str, str]) -> list[str]:
    errors: list[str] = []
    lexical_root = Path(os.path.abspath(root))
    for relative in CHECKED_MARKDOWN_FILES:
        text = texts.get(relative)
        if text is None:
            continue
        path = lexical_root / relative
        for link in markdown_links(text):
            target = markdown_link_target(link.target)
            if target is None:
                continue
            lexical_relative = lexical_repository_relative(
                lexical_root, path.parent / target
            )
            if lexical_relative is None:
                errors.append(f"{relative}: relative link escapes repository: {target}")
                continue
            lookup = lookup_repository_path(lexical_root, lexical_relative)
            if lookup.status == "escape":
                errors.append(f"{relative}: relative link escapes repository: {target}")
            elif lookup.status == "missing":
                errors.append(f"{relative}: broken relative link: {target}")
            elif lookup.status == "case-mismatch":
                errors.append(f"{relative}: relative link has incorrect path case: {target}")
            elif lookup.status == "ambiguous-case":
                errors.append(f"{relative}: relative link has ambiguous path case: {target}")
    return errors


def context_link_edges(root: Path, relative: str, texts: dict[str, str]) -> set[str]:
    lexical_root = Path(os.path.abspath(root))
    path = lexical_root / relative
    text = texts.get(relative)
    if text is None:
        return set()
    edges: set[str] = set()
    for link in markdown_links(text):
        if link.is_image:
            continue
        target = markdown_link_target(link.target)
        if target is None:
            continue
        target_relative = lexical_repository_relative(lexical_root, path.parent / target)
        if target_relative is None:
            continue
        lookup = lookup_repository_path(lexical_root, target_relative)
        if lookup.status != "ok" or lookup.path is None:
            continue
        actual_relative = lookup.path.relative_to(lexical_root).as_posix()
        if actual_relative in REACHABLE_CONTEXT_FILES:
            edges.add(actual_relative)
    return edges


def check_context_reachability(root: Path, texts: dict[str, str]) -> list[str]:
    reachable = {"AGENTS.md"}
    pending = ["AGENTS.md"]
    while pending:
        current = pending.pop()
        for target in context_link_edges(root, current, texts):
            if target not in reachable:
                reachable.add(target)
                pending.append(target)

    return [
        f"{relative}: agent context file is not reachable from AGENTS.md"
        for relative in sorted(REACHABLE_CONTEXT_FILES - reachable)
        if relative in texts
    ]


def just_callables(justfile: str) -> set[str]:
    callables: set[str] = set()
    name_pattern = r"[a-zA-Z_][a-zA-Z0-9_-]*"
    alias_pattern = re.compile(rf"^alias[ \t]+({name_pattern})[ \t]*:=")
    name_prefix = re.compile(rf"^({name_pattern})(.*)$")
    assignment_prefix = re.compile(r"^[ \t]*(?::=|\+=|\?=|=)")

    for line in justfile.splitlines():
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        if line.startswith("@"):
            line = line[1:]
        alias = alias_pattern.match(line)
        if alias:
            callables.add(alias.group(1))
            continue
        if line.startswith(("set ", "export ", "unexport ", "import ", "mod ")):
            continue
        header = name_prefix.match(line)
        if not header:
            continue
        remainder = header.group(2)
        if assignment_prefix.match(remainder):
            continue
        if remainder.lstrip().startswith("("):
            continue
        if any(
            character == ":" and remainder[index + 1 : index + 2] != "="
            for index, character in enumerate(remainder)
        ):
            callables.add(header.group(1))
    return callables


def check_documented_just_recipes(texts: dict[str, str]) -> list[str]:
    justfile = texts.get("justfile")
    if justfile is None:
        return []
    recipes = just_callables(justfile)
    errors: list[str] = []
    for relative in CHECKED_MARKDOWN_FILES:
        text = texts.get(relative)
        if text is None:
            continue
        for span in inline_code_spans(text):
            match = re.match(r"^\s*just\s+([^\s`]+)", span)
            if match is None:
                continue
            recipe = match.group(1)
            if any(character in recipe for character in "*?["):
                continue
            if recipe not in recipes:
                errors.append(f"{relative}: unknown just recipe: {recipe}")
    return errors


def repository_glob_lookup(root: Path, reference: str) -> str:
    parts = Path(reference).parts
    static_parts: list[str] = []
    for part in parts:
        if glob.has_magic(part):
            break
        static_parts.append(part)
    if static_parts:
        prefix = lookup_repository_path(root, Path(*static_parts))
        if prefix.status != "ok":
            return prefix.status

    matches = glob.glob(str(root / reference), recursive=True)
    if not matches:
        return "missing"
    saw_case_mismatch = False
    saw_ambiguous_case = False
    for match in matches:
        relative = lexical_repository_relative(root, Path(match))
        if relative is None:
            return "escape"
        lookup = lookup_repository_path(root, relative)
        if lookup.status == "escape":
            return "escape"
        if lookup.status == "case-mismatch":
            saw_case_mismatch = True
        elif lookup.status == "ambiguous-case":
            saw_ambiguous_case = True
        elif lookup.status != "ok":
            return "missing"
    if saw_ambiguous_case:
        return "ambiguous-case"
    if saw_case_mismatch:
        return "case-mismatch"
    return "ok"


def check_repository_path_references(root: Path, texts: dict[str, str]) -> list[str]:
    errors: list[str] = []
    root = Path(os.path.abspath(root))
    for relative in CHECKED_MARKDOWN_FILES:
        text = texts.get(relative)
        if text is None:
            continue
        for raw_reference in inline_code_spans(text):
            if not raw_reference.startswith(REPOSITORY_PATH_PREFIXES):
                continue
            if any(character in raw_reference for character in "<> \t"):
                continue
            reference = raw_reference.split("::", 1)[0]
            if reference in GENERATED_PATH_REFERENCES:
                continue
            lexical_relative = lexical_repository_relative(root, root / reference)
            if lexical_relative is None:
                status = "escape"
            elif glob.has_magic(reference):
                status = repository_glob_lookup(root, reference)
            else:
                status = lookup_repository_path(root, lexical_relative).status

            if status == "escape":
                errors.append(
                    f"{relative}: repository path reference escapes repository: {reference}"
                )
            elif status == "case-mismatch":
                errors.append(
                    f"{relative}: repository path reference has incorrect path case: {reference}"
                )
            elif status == "ambiguous-case":
                errors.append(
                    f"{relative}: repository path reference has ambiguous path case: {reference}"
                )
            elif status != "ok":
                errors.append(
                    f"{relative}: repository path reference is missing: {reference}"
                )
    return errors


def check_template_fields(texts: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for relative, expected_fields in TEMPLATE_FIELDS.items():
        text = texts.get(relative)
        if text is None:
            continue
        field_counts = Counter(AGENT_FIELD_RE.findall(text))
        fields = set(field_counts)
        for field in expected_fields:
            if field not in fields:
                errors.append(f"{relative}: missing template field: {field}")
        for field, count in sorted(field_counts.items()):
            if count > 1:
                errors.append(f"{relative}: duplicate template field: {field}")
    return errors


def parse_evidence_attributes(raw: str) -> tuple[dict[str, str], bool]:
    attributes: dict[str, str] = {}
    valid = True
    for item in raw.split():
        key, separator, value = item.partition("=")
        if not separator or not key or not value or key in attributes:
            valid = False
            continue
        attributes[key] = value
    return attributes, valid


def check_windows_evidence_contracts(root: Path, texts: dict[str, str]) -> list[str]:
    relative = "docs/development/windows.md"
    text = texts.get(relative)
    if text is None:
        return []
    markers: dict[str, list[tuple[dict[str, str], bool]]] = {}
    for evidence_id, raw_attributes in AGENT_EVIDENCE_RE.findall(
        strip_markdown_code(text)
    ):
        markers.setdefault(evidence_id, []).append(
            parse_evidence_attributes(raw_attributes)
        )

    errors: list[str] = []
    for evidence_id, expected in WINDOWS_EVIDENCE_CONTRACTS.items():
        contracts = markers.get(evidence_id, [])
        if not contracts:
            errors.append(f"{relative}: missing evidence contract: {evidence_id}")
            continue
        if len(contracts) > 1:
            errors.append(f"{relative}: duplicate evidence contract: {evidence_id}")
            continue
        contract, valid = contracts[0]
        if not valid or set(contract) != set(expected):
            errors.append(
                f"{relative}: {evidence_id} evidence contract has invalid attributes"
            )
            continue
        for key, value in expected.items():
            if contract.get(key) != value:
                errors.append(
                    f"{relative}: {evidence_id} evidence contract mismatch: {key}"
                )
        for source_key in ("command", "workflow"):
            source = expected.get(source_key)
            if source and not path_exists_with_exact_case(root, Path(source)):
                errors.append(f"{relative}: evidence source is missing: {source}")
    return errors


def check_agent_context(root: Path) -> list[str]:
    root = Path(os.path.abspath(root))
    texts, load_errors = load_required_context_files(root)
    errors = [
        *load_errors,
        *check_claude_import(root, texts),
        *check_local_instruction_inventory(root),
        *check_relative_markdown_links(root, texts),
        *check_context_reachability(root, texts),
        *check_documented_just_recipes(texts),
        *check_repository_path_references(root, texts),
        *check_template_fields(texts),
        *check_windows_evidence_contracts(root, texts),
    ]
    return sorted(errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = check_agent_context(args.root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("agent context check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
