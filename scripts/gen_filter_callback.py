"""
Generate scripts/filter_repo_callback.py from the merged replacements JSON.

PURPOSE
    This script reads a JSON mapping of real-to-synthetic identifiers from
    `/tmp/awd_merged_replacements.json` and emits the complete
    `scripts/filter_repo_callback.py` module used by `git filter-repo` for
    history rewriting.

    This is a ONE-OFF MAINTENANCE TOOL. It is NOT part of the regular
    development workflow. It exists to generate the filter-repo callback from
    a structured, auditable JSON source rather than maintaining the callback
    by hand.

USAGE
    1. Prepare the replacements JSON at `/tmp/awd_merged_replacements.json`
       (format: {"real_value": "synthetic_value", ...}).
    2. Run:

           python3 scripts/gen_filter_callback.py

    3. The script overwrites `scripts/filter_repo_callback.py` in place.
    4. Verify the generated file, then use it with `git filter-repo` as
       documented in that module's docstring.

EFFECT ON GIT HISTORY
    This script itself does NOT modify git history. It generates the callback
    module that `git filter-repo` uses to rewrite history. See
    `filter_repo_callback.py` for the history-rewrite effects.

RISK & GOVERNANCE
    - The generated callback performs a DESTRUCTIVE HISTORY REWRITE. Per
      OPERATING_RULES (command integrity), such operations require explicit
      human approval and must never be automated in CI/CD.
    - The input JSON (`/tmp/awd_merged_replacements.json`) is the source of
      truth. It must be audited for completeness and correctness before
      generating the callback. Missing mappings leak real data; incorrect
      mappings corrupt synthetic data.
    - This script must be run in a clean environment. The input path is
      hardcoded to `/tmp/awd_merged_replacements.json` to avoid accidental
      commits of real-data mappings.

MAINTENANCE
    The template (header/footer) in this file mirrors the structure of
    `filter_repo_callback.py`. If the callback API changes (e.g., new callback
    functions needed), update both the template here and the target module.
"""
import json
from pathlib import Path

pairs = json.loads(Path("/tmp/awd_merged_replacements.json").read_text())
lines = []
for k, v in pairs.items():
    kb = "b" + json.dumps(k)
    vb = "b" + json.dumps(v)
    lines.append(f"    {kb}: {vb},")

body = "\n".join(lines)

header = '"""git-filter-repo callbacks for autowebdelivery-public history rewrite.\n\nReplaces all real-business identifiers with synthetic equivalents across every\nblob and commit message, and rewrites original commit authors to the GitHub\nnoreply address. Keys are processed LONGEST-FIRST to avoid substring collisions\n(e.g. b"Central Dental Center" inside b"Central Dental Center").\n\nURL-class-preserving (v2.2.1): social profiles stay on their public platform\nwith synthetic handles, shorteners stay shorteners, maps URLs stay maps URLs,\nso website classifiers keep each fixture\'s original class.\n"""\n\nraw_replacements = {\n'

footer = '\n}\n\n_ORDERED_KEYS = sorted(raw_replacements.keys(), key=len, reverse=True)\n\n\ndef _replace_all(data):\n    for old in _ORDERED_KEYS:\n        if old in data:\n            data = data.replace(old, raw_replacements[old])\n    return data\n\n\ndef blob_callback(blob, metadata):\n    blob.data = _replace_all(blob.data)\n\n\ndef commit_callback(commit, metadata):\n    commit.message = _replace_all(commit.message)\n    if commit.author_email == b"iker.goni@users.noreply.github.com":\n        commit.author_name = b"Iker Go\\xc3\\xb1i"\n        commit.author_email = b"iker.goni@users.noreply.github.com"\n    if commit.committer_email == b"iker.goni@users.noreply.github.com":\n        commit.committer_name = b"Iker Go\\xc3\\xb1i"\n        commit.committer_email = b"iker.goni@users.noreply.github.com"\n\n\ndef tag_callback(tag, metadata):\n    tag.message = _replace_all(tag.message)\n'

out = Path(__file__).parent.parent / "scripts" / "filter_repo_callback.py"
out.write_text(header + body + footer)
print("escrito:", out, "con", len(pairs), "mapeos")
