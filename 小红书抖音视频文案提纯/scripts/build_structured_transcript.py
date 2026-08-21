#!/usr/bin/env python3
"""Build a Markdown skeleton for a purified original-style transcript."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_REPLACEMENTS = {
    "Cloud code": "Claude Code",
    "Cloud Code": "Claude Code",
    "Clod Code": "Claude Code",
    "Cloudecode": "Claude Code",
    "Clashcode": "Claude Code",
    "CloudCoder": "Claude Code",
    "Clang code": "Claude Code",
    "Code X": "Codex",
    "CodeX": "Codex",
    "notebookrm": "NotebookLM",
    "notebookLM": "NotebookLM",
    "NotebookRM": "NotebookLM",
    "Nano banana pro": "Nano Banana Pro",
    "SKILL": "Skill",
}


def clean_text(text: str) -> str:
    text = text.strip()
    for old, new in DEFAULT_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\d+):\s+(\d+)", r"\1:\2", text)
    text = re.sub(r"([。！？])。", r"\1", text)
    text = text.replace("对吧？对吧？", "对吧？")
    text = text.replace("是不是是不是", "是不是")
    return text


def parse_sections(raw: str | None) -> dict[int, tuple[int, str]]:
    if not raw:
        return {1: (2, "正文")}
    data = json.loads(raw)
    sections: dict[int, tuple[int, str]] = {}
    for item in data:
        line = int(item["line"])
        level = int(item.get("level", 2))
        title = str(item["title"]).strip()
        if line < 1 or level not in (2, 3) or not title:
            raise ValueError(f"Invalid section item: {item!r}")
        sections[line] = (level, title)
    return dict(sorted(sections.items()))


def slug(title: str) -> str:
    return (
        title.lower()
        .replace("：", "")
        .replace("，", "")
        .replace("、", "")
        .replace(" ", "-")
    )


def first_nonempty(lines: list[str]) -> str:
    for line in lines:
        if line.strip():
            return clean_text(line)[:80]
    return "结构化逐字稿"


def build_markdown(
    source: Path,
    title: str | None,
    sections: dict[int, tuple[int, str]],
    keep_before_first_section: bool,
) -> str:
    raw_lines = source.read_text(encoding="utf-8").splitlines()
    doc_title = title or "提纯版原文"

    out: list[str] = []
    out.append(f"# {doc_title}")
    out.append("")
    out.append("> 整理说明：本稿根据原始文字稿整理，保留原意、语气、关键判断、案例和论证链，去除寒暄、口水话、重复和明显残句。")
    out.append("")

    first_section_line = min(sections) if sections else 1

    for idx, raw in enumerate(raw_lines, start=1):
        if not keep_before_first_section and idx < first_section_line:
            continue
        if idx in sections:
            level, heading = sections[idx]
            out.append(f"{'#' * level} {heading}")
            out.append("")
        text = clean_text(raw)
        if text:
            out.append(text)
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Input transcript text file")
    parser.add_argument("--output", required=True, help="Output Markdown file")
    parser.add_argument("--title", help="Markdown H1 title")
    parser.add_argument("--sections-json", help='JSON list, e.g. [{"line":1,"level":2,"title":"大主题"},{"line":8,"level":3,"title":"小标题"}]')
    parser.add_argument(
        "--keep-before-first-section",
        action="store_true",
        help="Keep source lines before the first provided section",
    )
    args = parser.parse_args()

    source = Path(args.source).expanduser()
    output = Path(args.output).expanduser()
    sections = parse_sections(args.sections_json)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_markdown(source, args.title, sections, args.keep_before_first_section),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
