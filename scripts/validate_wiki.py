#!/usr/bin/env python3
"""Validate the retrieval contract for the Grade 10 Mathematics wiki.

This intentionally uses only the Python standard library so it can run in the empty
repository before the server/content pipeline exists.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBJECT_ROOT = ROOT / "wiki" / "grade-10" / "core-mathematics"
STRANDS = SUBJECT_ROOT / "strands"
SUBSTRANDS = SUBJECT_ROOT / "sub-strands"
GRAPH_PATH = ROOT / "wiki" / "grade-10" / "core-mathematics" / "graph.json"

REQUIRED_HEADINGS = (
    "## Curriculum alignment",
    "## Knowledge graph",
    "## Teacher pack",
    "## Worked example",
    "## SMS teaching pack",
    "## Review notes",
)
STRAND_REQUIRED_HEADINGS = ("## Strand focus", "## Sub-strands", "## Teacher use", "## Review notes")
LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
ID_LINE = re.compile(r"^id:\s*(\S+)\s*$", re.MULTILINE)
TYPE_LINE = re.compile(r"^type:\s*(\S+)\s*$", re.MULTILINE)
CURRICULUM_LINE = re.compile(r"^curriculum_ref:\s*(\S+)\s*$", re.MULTILINE)
STRAND_LINE = re.compile(r"^strand_id:\s*(\S+)\s*$", re.MULTILINE)


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    if not GRAPH_PATH.exists():
        fail(f"missing graph: {GRAPH_PATH}", errors)
        print("wiki validation failed")
        print(" - " + "\n - ".join(errors))
        return 1

    try:
        graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"graph is not valid JSON: {exc}", errors)
        print("wiki validation failed")
        print(" - " + "\n - ".join(errors))
        return 1

    nodes = graph.get("nodes", [])
    node_by_id = {node.get("id"): node for node in nodes}
    if len(node_by_id) != len(nodes):
        fail("graph contains duplicate node IDs", errors)

    sub_nodes = [node for node in nodes if node.get("type") == "sub-strand"]
    if len(sub_nodes) != 14:
        fail(f"expected 14 sub-strand nodes, found {len(sub_nodes)}", errors)

    strand_nodes = [node for node in nodes if node.get("type") == "strand"]
    if len(strand_nodes) != 3:
        fail(f"expected 3 strand nodes, found {len(strand_nodes)}", errors)
    for node in strand_nodes:
        path = node.get("path")
        if not path:
            fail(f"strand node {node.get('id')} is missing a teacher-facing path", errors)
        elif not (SUBJECT_ROOT / path).exists():
            fail(f"strand node {node.get('id')} has a missing path: {path}", errors)

    for edge in graph.get("edges", []):
        if edge.get("from") not in node_by_id:
            fail(f"edge has unknown from node: {edge.get('from')}", errors)
        if edge.get("to") not in node_by_id:
            fail(f"edge has unknown to node: {edge.get('to')}", errors)

    page_ids: set[str] = set()
    pages = sorted(SUBSTRANDS.glob("M-*.md"))
    if len(pages) != 14:
        fail(f"expected 14 sub-strand pages, found {len(pages)}", errors)

    for page in pages:
        text = page.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            fail(f"{page}: missing YAML frontmatter", errors)
            continue
        metadata = match.group(1)
        page_id_match = ID_LINE.search(metadata)
        curriculum_match = CURRICULUM_LINE.search(metadata)
        strand_match = STRAND_LINE.search(metadata)
        page_id = page_id_match.group(1) if page_id_match else None
        if not page_id:
            fail(f"{page}: missing id", errors)
            continue
        if page_id in page_ids:
            fail(f"duplicate page id: {page_id}", errors)
        page_ids.add(page_id)
        node = node_by_id.get(page_id)
        if not node or node.get("type") != "sub-strand":
            fail(f"{page}: id {page_id} is not a sub-strand node in graph", errors)
        elif node.get("path") != str(page.relative_to(SUBSTRANDS.parent)):
            fail(f"{page}: graph path does not match page location", errors)
        if not curriculum_match:
            fail(f"{page}: missing curriculum_ref", errors)
        if not strand_match:
            fail(f"{page}: missing strand_id", errors)
        for heading in REQUIRED_HEADINGS:
            if heading not in text:
                fail(f"{page}: missing required section {heading}", errors)

        for sms in re.findall(r"^\*\*SMS [123]/3:\*\* (.+)$", text, re.MULTILINE):
            if len(sms) > 160:
                fail(f"{page}: SMS exceeds 160 characters ({len(sms)})", errors)

        for target in LOCAL_LINK.findall(text):
            clean_target = target.split("#", 1)[0]
            target_path = (page.parent / clean_target).resolve()
            if not target_path.exists():
                fail(f"{page}: broken local link {target}", errors)

    strand_page_ids: set[str] = set()
    strand_pages = sorted(STRANDS.glob("M-*.md"))
    if len(strand_pages) != 3:
        fail(f"expected 3 strand pages, found {len(strand_pages)}", errors)

    for page in strand_pages:
        text = page.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            fail(f"{page}: missing YAML frontmatter", errors)
            continue
        metadata = match.group(1)
        page_id_match = ID_LINE.search(metadata)
        type_match = TYPE_LINE.search(metadata)
        curriculum_match = CURRICULUM_LINE.search(metadata)
        page_id = page_id_match.group(1) if page_id_match else None
        if not page_id:
            fail(f"{page}: missing id", errors)
            continue
        if page_id in strand_page_ids:
            fail(f"duplicate strand page id: {page_id}", errors)
        strand_page_ids.add(page_id)
        node = node_by_id.get(page_id)
        if not node or node.get("type") != "strand":
            fail(f"{page}: id {page_id} is not a strand node in graph", errors)
        elif node.get("path") != str(page.relative_to(SUBJECT_ROOT)):
            fail(f"{page}: graph path does not match page location", errors)
        if not type_match or type_match.group(1) != "strand":
            fail(f"{page}: metadata type must be strand", errors)
        if not curriculum_match:
            fail(f"{page}: missing curriculum_ref", errors)
        for heading in STRAND_REQUIRED_HEADINGS:
            if heading not in text:
                fail(f"{page}: missing required section {heading}", errors)
        for target in LOCAL_LINK.findall(text):
            clean_target = target.split("#", 1)[0]
            target_path = (page.parent / clean_target).resolve()
            if not target_path.exists():
                fail(f"{page}: broken local link {target}", errors)

    graph_strand_ids = {node.get("id") for node in strand_nodes}
    if strand_page_ids != graph_strand_ids:
        fail(
            "strand page IDs and graph strand IDs differ: "
            f"pages-only={sorted(strand_page_ids - graph_strand_ids)}, "
            f"graph-only={sorted(graph_strand_ids - strand_page_ids)}",
            errors,
        )

    graph_page_ids = {node.get("id") for node in sub_nodes}
    if page_ids != graph_page_ids:
        fail(
            "page IDs and graph sub-strand IDs differ: "
            f"pages-only={sorted(page_ids - graph_page_ids)}, "
            f"graph-only={sorted(graph_page_ids - page_ids)}",
            errors,
        )

    if errors:
        print("wiki validation failed")
        print(" - " + "\n - ".join(errors))
        return 1

    print(f"wiki validation passed: {len(nodes)} nodes, {len(graph.get('edges', []))} edges, {len(pages)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
