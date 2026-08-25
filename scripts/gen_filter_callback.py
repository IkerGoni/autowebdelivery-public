"""Generate scripts/filter_repo_callback.py from the merged replacements JSON."""
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
