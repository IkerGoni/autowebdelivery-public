#!/usr/bin/env python
"""Regenerate C1 fixtures with 18 synthetic dental clinics (DEV PLAN v2.2, D1/A1).

Scope: the three fixture families touched by the plan:
  - tests/fixtures/phase_02_basic_lead_discovery/
  - tests/fixtures/phase_02_1_website_filter/
  - tests/fixtures/phase_02/

Method:
  1. Apply the raw_replacements mapping from the D2 filter-repo callback
     (LONGEST-FIRST order) as plain text replacement over every file in the
     three families. The four *derived-slug* keys of the callback are
     deliberately EXCLUDED here: slugs are repaired structurally in step 2,
     which is strictly more accurate than text substitution.
  2. Repair every ``business_slug`` value so it matches what the real
     pipeline would produce (make_business_slug from
     packages/phases/phase_02_basic_lead_discovery.py):
       - records that carry ``business_name`` get their slug recomputed
         directly from (business_name, record id);
       - records without a name (website classifications) get their slug
         base translated through the 18-name bijection table, keeping the
         record-id suffix.
  3. Integrated verification (empirical evidence, not self-report):
       - pre-pass sanity: real tokens ARE present before rewriting;
       - post-pass: zero real tokens remain in the three families
         (including non-synthetic ChIJ* place ids);
       - positive: all 18 synthetic names present;
       - consistency: every business_slug equals make_business_slug(...)
         recomputed live;
       - idempotency: a second execution changes nothing.

The script is idempotent and exits non-zero on any failed assertion.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
FAMILIES = (
    "phase_02_basic_lead_discovery",
    "phase_02_1_website_filter",
    "phase_02",
)

# ---------------------------------------------------------------------------
# raw_replacements (D2 callback) — verbatim from state/plans/awd-hardening/PLAN.md
# minus the four derived-slug keys (handled structurally below).
# ---------------------------------------------------------------------------
RAW_REPLACEMENTS = {
    # === BUSINESS NAMES (18 groups) ===
    "Central Dental Center": "Central Dental Center",
    "Bright Smile Dental Clinic": "Bright Smile Dental Clinic",
    "Meridian Dental Care": "Meridian Dental Care",
    "Meridian Dental Care": "Meridian Dental Care",
    "Riverfront Dental Studio": "Riverfront Dental Studio",
    "Pearl Wave Dental Clinic": "Pearl Wave Dental Clinic",
    "Royal Crown Dental": "Royal Crown Dental",
    "Smile Artisan Dental": "Smile Artisan Dental",
    "Bastion Dental Care": "Bastion Dental Care",
    "Lotus Wing Dental Lab": "Lotus Wing Dental Lab",
    "Chiang Mai Dental Park": "Chiang Mai Dental Park",
    "Northgate Dental Clinic": "Northgate Dental Clinic",
    "Eastbank Dental Lab": "Eastbank Dental Lab",
    "Cedar Grove Dental Clinic": "Cedar Grove Dental Clinic",
    "Nova Dental Clinic": "Nova Dental Clinic",
    "Value Dental Care": "Value Dental Care",
    "Harborview Dental Care": "Harborview Dental Care",
    "Grin House Dental": "Grin House Dental",
    "Social Smile Dental": "Social Smile Dental",
    "Central Dental Center": "Central Dental Center",
    # === REAL DOMAINS ===
    "meridiandentalcare.example": "meridiandentalcare.example",
    "brightsmile-dental.example": "brightsmile-dental.example",
    "centraldentalcenter.example": "centraldentalcenter.example",
    "novadentalclinic.example": "novadentalclinic.example",
    "valuedentalcare.example": "valuedentalcare.example",
    "riverfrontdental.example": "riverfrontdental.example",
    "centraldentalcenter.example": "centraldentalcenter.example",
    "brightsmile-dental.example": "brightsmile-dental.example",
    # === SOCIAL PROFILE URLS (class-preserving: platform stays public, handle synthetic) ===
    "facebook.com/chiangmaidentalpark": "facebook.com/chiangmaidentalpark",
    "facebook.com/northgatedental": "facebook.com/northgatedental",
    "facebook.com/centraldentalcm": "facebook.com/centraldentalcm",
    "facebook.com/riverfrontdental": "facebook.com/riverfrontdental",
    "instagram.com/cedargrovedental": "instagram.com/cedargrovedental",
    "instagram.com/socialsmiledental": "instagram.com/socialsmiledental",
    # === SHORTLINKS (class-preserving) ===
    "bit.ly/grin-house-dental": "bit.ly/grin-house-dental",
    # === UNCERTAIN MAPS URLS (class-preserving; DoD#3 only bans ?cid=oldtown) ===
    "maps.google.com/?cid=synthetic0001": "maps.google.com/?cid=synthetic0001",
    # === EXTRA ADDRESSES (v2.1) ===
    "145 Dockside Avenue, Bangkok 10500, Thailand": "145 Dockside Avenue, Bangkok 10500, Thailand",
    "9 Southgate Lane, Chiang Mai 50200, Thailand": "9 Southgate Lane, Chiang Mai 50200, Thailand",
    # === REAL ADDRESSES (20) ===
    "123 Maplewood Rd, Chiang Mai 50200": "123 Maplewood Rd, Chiang Mai 50200",
    "15 Birchwood Rd, Chiang Mai 50200": "15 Birchwood Rd, Chiang Mai 50200",
    "15/3 Birchwood Rd, Chiang Mai 50200": "15/3 Birchwood Rd, Chiang Mai 50200",
    "142 Lakeshore Rd, Chiang Mai 50100": "142 Lakeshore Rd, Chiang Mai 50100",
    "22 Hillcrest Rd, Chiang Mai 50300": "22 Hillcrest Rd, Chiang Mai 50300",
    "99 Dockside Rd, Chiang Mai 50000": "99 Dockside Rd, Chiang Mai 50000",
    "8 Cedarbrook Rd, Chiang Mai 50000": "8 Cedarbrook Rd, Chiang Mai 50000",
    "55 Fernhill Rd, Chiang Mai 50200": "55 Fernhill Rd, Chiang Mai 50200",
    "2 Stonebridge Rd, Chiang Mai 50200": "2 Stonebridge Rd, Chiang Mai 50200",
    "44 Kingsway Rd, Chiang Mai 50200": "44 Kingsway Rd, Chiang Mai 50200",
    "123 Maplewood Rd, Chiang Mai": "123 Maplewood Rd, Chiang Mai",
    "456 Southgate Rd, Chiang Mai": "456 Southgate Rd, Chiang Mai",
    "789 Eastport Rd, Chiang Mai": "789 Eastport Rd, Chiang Mai",
    "101 Bastion Rd, Chiang Mai": "101 Bastion Rd, Chiang Mai",
    "202 Market Square, Chiang Mai": "202 Market Square, Chiang Mai",
    "321 Ashford Rd, Chiang Mai": "321 Ashford Rd, Chiang Mai",
    "654 Greenfield Rd, Chiang Mai": "654 Greenfield Rd, Chiang Mai",
    "321 Harborview Rd, Chiang Mai": "321 Harborview Rd, Chiang Mai",
    "101 Sunrise St, Chiang Mai": "101 Sunrise St, Chiang Mai",
    "202 Union St, Chiang Mai": "202 Union St, Chiang Mai",
    # === REAL PLACE IDS (22) ===
    "ChIJSYNTHETIC00000000000000001": "ChIJSYNTHETIC00000000000000001",
    "ChIJSYNTHETIC00000000000000002": "ChIJSYNTHETIC00000000000000002",
    "ChIJSYNTHETIC00000000000000003": "ChIJSYNTHETIC00000000000000003",
    "ChIJSYNTHETIC00000000000000004": "ChIJSYNTHETIC00000000000000004",
    "ChIJSYNTHETIC00000000000000005": "ChIJSYNTHETIC00000000000000005",
    "ChIJSYNTHETIC00000000000000006": "ChIJSYNTHETIC00000000000000006",
    "ChIJSYNTHETIC00000000000000007": "ChIJSYNTHETIC00000000000000007",
    "ChIJSYNTHETIC00000000000000008": "ChIJSYNTHETIC00000000000000008",
    "ChIJSYNTHETIC00000000000000009": "ChIJSYNTHETIC00000000000000009",
    "ChIJSYNTHETIC00000000000000010": "ChIJSYNTHETIC00000000000000010",
    "ChIJSYNTHETIC00000000000000011": "ChIJSYNTHETIC00000000000000011",
    "ChIJSYNTHETIC00000000000000012": "ChIJSYNTHETIC00000000000000012",
    "ChIJSYNTHETIC00000000000000013": "ChIJSYNTHETIC00000000000000013",
    "ChIJSYNTHETIC00000000000000015": "ChIJSYNTHETIC00000000000000015",
    "ChIJSYNTHETIC00000000000000014": "ChIJSYNTHETIC00000000000000014",
    "ChIJSYNTHETIC00000000000000016": "ChIJSYNTHETIC00000000000000016",
    "ChIJSYNTHETIC00000000000000017": "ChIJSYNTHETIC00000000000000017",
    "ChIJSYNTHETIC00000000000000018": "ChIJSYNTHETIC00000000000000018",
    "ChIJSYNTHETIC00000000000000019": "ChIJSYNTHETIC00000000000000019",
    "ChIJSYNTHETIC00000000000000020": "ChIJSYNTHETIC00000000000000020",
    "ChIJSYNTHETIC00000000000000021": "ChIJSYNTHETIC00000000000000021",
    "ChIJSYNTHETIC00000000000000022": "ChIJSYNTHETIC00000000000000022",
    # === REAL PHONES (18) ===
    "+66 53 000 001": "+66 53 000 001",
    "+66 2 555 0101": "+66 2 555 0101",
    "+66 2 555 0102": "+66 2 555 0102",
    "+66 53 000 002": "+66 53 000 002",
    "+66 53 000 003": "+66 53 000 003",
    "+66 53 000 004": "+66 53 000 004",
    "+66 53 000 005": "+66 53 000 005",
    "+66 53 000 006": "+66 53 000 006",
    "+66 53 000 007": "+66 53 000 007",
    "+66 53 000 008": "+66 53 000 008",
    "+66 53 000 009": "+66 53 000 009",
    "+66 53 000 010": "+66 53 000 010",
    "+66 53 000 011": "+66 53 000 011",
    "+66 53 000 012": "+66 53 000 012",
    "+66 53 000 013": "+66 53 000 013",
    "+66 53 000 014": "+66 53 000 014",
    "+66 53 000 015": "+66 53 000 015",
    "+66 53 000 016": "+66 53 000 016",
    # === OTHER SENSIBLE DATA ===
    "192.0.2.1": "192.0.2.1",
    "iker.goni@users.noreply.github.com": "iker.goni@users.noreply.github.com",
    "/home/user/project": "/home/user/project",
    "/Users/demo/": "/Users/demo/",
}

# 18-name bijection (D1 table): real -> synthetic, used for slug-base repair.
NAME_BIJECTION = {
    "Bright Smile Dental Clinic": "Bright Smile Dental Clinic",
    "Meridian Dental Care": "Meridian Dental Care",
    "Central Dental Center": "Central Dental Center",
    "Riverfront Dental Studio": "Riverfront Dental Studio",
    "Nova Dental Clinic": "Nova Dental Clinic",
    "Value Dental Care": "Value Dental Care",
    "Pearl Wave Dental Clinic": "Pearl Wave Dental Clinic",
    "Royal Crown Dental": "Royal Crown Dental",
    "Harborview Dental Care": "Harborview Dental Care",
    "Grin House Dental": "Grin House Dental",
    "Social Smile Dental": "Social Smile Dental",
    "Chiang Mai Dental Park": "Chiang Mai Dental Park",
    "Northgate Dental Clinic": "Northgate Dental Clinic",
    "Eastbank Dental Lab": "Eastbank Dental Lab",
    "Cedar Grove Dental Clinic": "Cedar Grove Dental Clinic",
    "Smile Artisan Dental": "Smile Artisan Dental",
    "Bastion Dental Care": "Bastion Dental Care",
    "Lotus Wing Dental Lab": "Lotus Wing Dental Lab",
}

SLUG_SUFFIX_RE = re.compile(r"^(.*)-([A-Za-z0-9]{3,6})$")
PLACE_ID_REAL_RE = re.compile(r"ChIJ(?!SYNTHETIC)[0-9A-Za-z_-]+")


def base_slug(name: str) -> str:
    """Name part of make_business_slug (same rules, no record-id suffix)."""
    import unicodedata

    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:50].rstrip("-")


SLUG_BASE_MAP = {base_slug(k): base_slug(v) for k, v in NAME_BIJECTION.items()}


def iter_family_files():
    for fam in FAMILIES:
        yield from sorted(p for p in (FIXTURES / fam).rglob("*") if p.is_file())


def apply_replacements(text: str) -> str:
    for old in sorted(RAW_REPLACEMENTS, key=len, reverse=True):
        text = text.replace(old, RAW_REPLACEMENTS[old])
    return text


def walk_records(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_records(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_records(item)


def slug_fix_pairs(json_text: str) -> dict[str, str]:
    """Discover business_slug corrections required in a (already replaced) doc."""
    fixes: dict[str, str] = {}
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return fixes
    for rec in walk_records(data):
        slug = rec.get("business_slug")
        if not isinstance(slug, str) or not slug:
            continue
        name = rec.get("business_name")
        if isinstance(name, str) and name:
            rid = rec.get("raw_record_id") or rec.get("record_id") or ""
            target = make_business_slug(name, str(rid))
        else:
            m = SLUG_SUFFIX_RE.match(slug)
            if not m:
                continue
            base, suffix = m.groups()
            new_base = SLUG_BASE_MAP.get(base)
            if new_base is None:
                continue
            target = f"{new_base}-{suffix}"
        if target != slug:
            fixes.setdefault(slug, target)
    return fixes


def scan_real_tokens() -> dict[str, int]:
    """Count remaining real tokens across the three families."""
    hits: dict[str, int] = {}
    for path in iter_family_files():
        raw = path.read_bytes()
        if b"\x00" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        for old in RAW_REPLACEMENTS:
            n = text.count(old)
            if n:
                hits[f"{path.relative_to(REPO)} :: {old}"] = n
        for pid in PLACE_ID_REAL_RE.findall(text):
            key = f"{path.relative_to(REPO)} :: PLACE_ID:{pid}"
            hits[key] = hits.get(key, 0) + text.count(pid)
    return hits


def main() -> int:
    sys.path.insert(0, str(REPO / "packages"))
    global make_business_slug
    from phases.phase_02_basic_lead_discovery import make_business_slug  # noqa: E402

    # Bijection sanity: no base may be simultaneously an old and a new base.
    overlap = set(SLUG_BASE_MAP) & set(SLUG_BASE_MAP.values())
    assert not overlap, f"slug base collision: {overlap}"

    files = list(iter_family_files())
    print(f"[1] family files in scope: {len(files)}")

    pre = scan_real_tokens()
    pre_total = sum(pre.values())
    assert pre_total > 0, "sanity FAILED: no real tokens found before regeneration"
    print(f"[2] pre-pass sanity: {pre_total} real-token occurrences (dirty input confirmed)")

    changed_files = 0
    for path in files:
        original = path.read_text(encoding="utf-8")
        updated = apply_replacements(original)
        for old_slug, new_slug in slug_fix_pairs(updated).items():
            updated = updated.replace(f'"{old_slug}"', f'"{new_slug}"')
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files += 1

    print(f"[3] files rewritten: {changed_files}")

    post = scan_real_tokens()
    assert not post, f"verification FAILED, real tokens remain: {post}"
    print("[4] post-pass: 0 real-token occurrences in the three families")

    synth_names = sorted(set(NAME_BIJECTION.values()))
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in files)
    missing = [n for n in synth_names if n not in corpus]
    assert not missing, f"verification FAILED, missing synthetic names: {missing}"
    print(f"[5] positive check: all {len(synth_names)} synthetic names present")

    bad_slugs = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for rec in walk_records(data):
            slug = rec.get("business_slug")
            name = rec.get("business_name")
            if isinstance(slug, str) and isinstance(name, str) and slug and name:
                rid = str(rec.get("raw_record_id") or rec.get("record_id") or "")
                if slug != make_business_slug(name, rid):
                    bad_slugs.append((str(path.relative_to(REPO)), name, slug))
    assert not bad_slugs, f"consistency FAILED, slugs diverge from pipeline code: {bad_slugs[:5]}"
    print("[6] consistency: every business_slug matches make_business_slug() output")

    snapshot = {p: p.read_bytes() for p in files}
    for path in files:
        text = path.read_text(encoding="utf-8")
        text = apply_replacements(text)
        for old_slug, new_slug in slug_fix_pairs(text).items():
            text = text.replace(f'"{old_slug}"', f'"{new_slug}"')
        assert text.encode("utf-8") == snapshot[path], f"idempotency FAILED: {path}"
    print("[7] idempotency: second pass changes nothing")

    print("OK: fixtures regenerated and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
