#!/usr/bin/env python3
"""Template inventory + raw hardcoded-literal scan (Sprint S0-T3).

Read-only analysis of packages/templates/modular/sections/** and
packages/templates/stitch_prompts/*.md. Emits a JSON inventory with
per-file counts of suspicious hardcoded literals as raw data for
Sprint S1 (factual safety at the source). This script fixes nothing.

Usage:
    python3 scripts/inventory_templates.py                # JSON to stdout
    python3 scripts/inventory_templates.py -o out.json    # JSON to file

Stdlib only. Always exits 0 on successful scan.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECTIONS_DIR = PROJECT_ROOT / "packages" / "templates" / "modular" / "sections"
PROMPTS_DIR = PROJECT_ROOT / "packages" / "templates" / "stitch_prompts"

PATTERNS: dict[str, re.Pattern[str]] = {
    "fake_contact": re.compile(r"business@email\.com", re.IGNORECASE),
    "price_literal": re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?"),
    "phone_literal": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    "rating_literal": re.compile(r"\b\d\.\d\b(?=\s*(?:★|star|/5|from|rating)?)", re.IGNORECASE),
    "review_count": re.compile(r"\b\d{2,}\+?\s*(?:verified\s+)?reviews\b", re.IGNORECASE),
    "unresolved_placeholder": re.compile(r"\{\{(?!\s*\w+\s*\}\})[^\n]{0,40}"),
    "proper_noun_phrase": re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
}

SAMPLE_CAP = 5


def classify_section(path: Path) -> dict[str, str]:
    """Classify a section file by family / variant / device from its path."""
    rel = path.relative_to(SECTIONS_DIR)
    family = rel.parts[0]
    variant = ".".join(rel.parts[1:-1]) if len(rel.parts) > 2 else "root"
    name = path.stem.lower()
    if "_mobile" in name or "mobile" in variant:
        device = "mobile"
    elif "_desktop" in name or "desktop" in variant:
        device = "desktop"
    else:
        device = "shared"
    return {"family": family, "variant": variant, "device": device}


def scan_file(path: Path, rel_root: Path) -> dict[str, object]:
    """Scan one file and return per-pattern counts plus small samples."""
    text = path.read_text(encoding="utf-8", errors="replace")
    entry: dict[str, object] = {"file": str(path.relative_to(rel_root))}
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for label, pattern in PATTERNS.items():
        matches = pattern.findall(text)
        counts[label] = len(matches)
        if matches and label in {"fake_contact", "price_literal", "phone_literal", "rating_literal", "review_count"}:
            samples[label] = sorted(set(matches))[:SAMPLE_CAP]
    entry["counts"] = counts
    if samples:
        entry["samples"] = samples
    return entry


def build_inventory() -> dict[str, object]:
    sections: list[dict[str, object]] = []
    if SECTIONS_DIR.is_dir():
        for path in sorted(SECTIONS_DIR.rglob("*.html")):
            entry = scan_file(path, PROJECT_ROOT)
            entry.update(classify_section(path))
            sections.append(entry)

    prompts: list[dict[str, object]] = []
    if PROMPTS_DIR.is_dir():
        for path in sorted(PROMPTS_DIR.glob("*.md")):
            prompts.append(scan_file(path, PROJECT_ROOT))

    def total(entries: list[dict[str, object]], label: str) -> int:
        return sum(int(e["counts"][label]) for e in entries)  # type: ignore[index]

    summary = {
        "section_files": len(sections),
        "families": sorted({str(e["family"]) for e in sections}),  # type: ignore[index]
        "fake_contact_total": total(sections, "fake_contact"),
        "price_literal_total": total(sections, "price_literal"),
        "phone_literal_total": total(sections, "phone_literal"),
        "prompt_files": len(prompts),
        "prompt_price_total": total(prompts, "price_literal"),
    }
    return {"summary": summary, "sections": sections, "stitch_prompts": prompts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=None, help="write JSON here instead of stdout")
    args = parser.parse_args()

    inventory = build_inventory()
    payload = json.dumps(inventory, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"inventory written to {args.output}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
