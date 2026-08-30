"""
git-filter-repo callbacks for autowebdelivery-public history rewrite.

PURPOSE
    This module provides the callback functions used by `git filter-repo` to
    rewrite the entire repository history, replacing all real-business
    identifiers (names, addresses, phones, domains, social handles, place IDs,
    emails, paths) with synthetic equivalents. It also normalizes commit authors
    to the GitHub noreply address.

    This is a ONE-OFF MAINTENANCE TOOL. It is NOT part of the regular
    development workflow. It exists solely to sanitize the public repository
    history for open-source publication, ensuring no real business data leaks
    into git blobs, commit messages, or author metadata.

USAGE
    This module is NOT executed directly. It is invoked by `git filter-repo`:

        git filter-repo --commit-callback scripts/filter_repo_callback.py \
                        --blob-callback scripts/filter_repo_callback.py \
                        --tag-name-callback scripts/filter_repo_callback.py \
                        --tag-message-callback scripts/filter_repo_callback.py \
                        --force

    The `--force` flag is required because this rewrites history destructively.

EFFECT ON GIT HISTORY
    - REWRITES ALL COMMIT HASHES: every commit in the repository gets a new SHA.
    - REWRITES ALL BLOB CONTENTS: every file at every revision is rewritten.
    - REWRITES ALL TAGS: tag messages and names are filtered.
    - CHANGES AUTHOR/COMMITTER INFO: all commits are attributed to the GitHub
      noreply address (iker.goni@users.noreply.github.com).
    - THIS IS IRREVERSIBLE without a backup or reflog recovery.

    After running, ALL COLLABORATORS MUST RE-CLONE. Force-pushing the rewritten
    history (`git push --force --all && git push --force --tags`) invalidates
    every existing clone.

RISK & GOVERNANCE
    - This script implements a DESTRUCTIVE HISTORY REWRITE. Per OPERATING_RULES
      (command integrity), such operations require explicit human approval and
      must never be automated in CI/CD.
    - The replacement mapping (`raw_replacements`) must be audited before use.
      Missing or incorrect mappings will leave real data in history or corrupt
      synthetic data.
    - Key ordering (LONGEST-FIRST) prevents substring collisions (e.g.,
      "Central Dental Center" must be replaced before "Central Dental").

URL-CLASS PRESERVATION (v2.2.1)
    Social profile URLs retain their public platform (facebook.com, instagram.com)
    with synthetic handles. URL shorteners (bit.ly) remain shorteners. Maps URLs
    (maps.google.com) retain their class. This preserves fixture validity for
    website classifiers that depend on URL structure.

MAINTENANCE
    To update the replacement map, edit the JSON source at
    `/tmp/awd_merged_replacements.json` and regenerate this file via:

        python3 scripts/gen_filter_callback.py

    Do NOT hand-edit the `raw_replacements` dict in this file; it is generated.
"""

raw_replacements = {
    b"Central Dental Center": b"Central Dental Center",
    b"Bright Smile Dental Clinic": b"Bright Smile Dental Clinic",
    b"Meridian Dental Care": b"Meridian Dental Care",
    b"Riverfront Dental Studio": b"Riverfront Dental Studio",
    b"Pearl Wave Dental Clinic": b"Pearl Wave Dental Clinic",
    b"Royal Crown Dental": b"Royal Crown Dental",
    b"Smile Artisan Dental": b"Smile Artisan Dental",
    b"Bastion Dental Care": b"Bastion Dental Care",
    b"Lotus Wing Dental Lab": b"Lotus Wing Dental Lab",
    b"Chiang Mai Dental Park": b"Chiang Mai Dental Park",
    b"Northgate Dental Clinic": b"Northgate Dental Clinic",
    b"Eastbank Dental Lab": b"Eastbank Dental Lab",
    b"Cedar Grove Dental Clinic": b"Cedar Grove Dental Clinic",
    b"Nova Dental Clinic": b"Nova Dental Clinic",
    b"Value Dental Care": b"Value Dental Care",
    b"Harborview Dental Care": b"Harborview Dental Care",
    b"Grin House Dental": b"Grin House Dental",
    b"Social Smile Dental": b"Social Smile Dental",
    b"meridiandentalcare.example": b"meridiandentalcare.example",
    b"brightsmile-dental.example": b"brightsmile-dental.example",
    b"centraldentalcenter.example": b"centraldentalcenter.example",
    b"novadentalclinic.example": b"novadentalclinic.example",
    b"valuedentalcare.example": b"valuedentalcare.example",
    b"riverfrontdental.example": b"riverfrontdental.example",
    b"facebook.com/chiangmaidentalpark": b"facebook.com/chiangmaidentalpark",
    b"facebook.com/northgatedental": b"facebook.com/northgatedental",
    b"facebook.com/centraldentalcm": b"facebook.com/centraldentalcm",
    b"facebook.com/riverfrontdental": b"facebook.com/riverfrontdental",
    b"instagram.com/cedargrovedental": b"instagram.com/cedargrovedental",
    b"instagram.com/socialsmiledental": b"instagram.com/socialsmiledental",
    b"bit.ly/grin-house-dental": b"bit.ly/grin-house-dental",
    b"maps.google.com/?cid=synthetic0001": b"maps.google.com/?cid=synthetic0001",
    b"bright-smile-dental-clinic": b"bright-smile-dental-clinic",
    b"social-smile": b"social-smile",
    b"harborview-dental": b"harborview-dental",
    b"grin-house": b"grin-house",
    b"145 Dockside Avenue, Bangkok 10500, Thailand": b"145 Dockside Avenue, Bangkok 10500, Thailand",
    b"9 Southgate Lane, Chiang Mai 50200, Thailand": b"9 Southgate Lane, Chiang Mai 50200, Thailand",
    b"123 Maplewood Rd, Chiang Mai 50200": b"123 Maplewood Rd, Chiang Mai 50200",
    b"15 Birchwood Rd, Chiang Mai 50200": b"15 Birchwood Rd, Chiang Mai 50200",
    b"15/3 Birchwood Rd, Chiang Mai 50200": b"15/3 Birchwood Rd, Chiang Mai 50200",
    b"142 Lakeshore Rd, Chiang Mai 50100": b"142 Lakeshore Rd, Chiang Mai 50100",
    b"22 Hillcrest Rd, Chiang Mai 50300": b"22 Hillcrest Rd, Chiang Mai 50300",
    b"99 Dockside Rd, Chiang Mai 50000": b"99 Dockside Rd, Chiang Mai 50000",
    b"8 Cedarbrook Rd, Chiang Mai 50000": b"8 Cedarbrook Rd, Chiang Mai 50000",
    b"55 Fernhill Rd, Chiang Mai 50200": b"55 Fernhill Rd, Chiang Mai 50200",
    b"2 Stonebridge Rd, Chiang Mai 50200": b"2 Stonebridge Rd, Chiang Mai 50200",
    b"44 Kingsway Rd, Chiang Mai 50200": b"44 Kingsway Rd, Chiang Mai 50200",
    b"123 Maplewood Rd, Chiang Mai": b"123 Maplewood Rd, Chiang Mai",
    b"456 Southgate Rd, Chiang Mai": b"456 Southgate Rd, Chiang Mai",
    b"789 Eastport Rd, Chiang Mai": b"789 Eastport Rd, Chiang Mai",
    b"101 Bastion Rd, Chiang Mai": b"101 Bastion Rd, Chiang Mai",
    b"202 Market Square, Chiang Mai": b"202 Market Square, Chiang Mai",
    b"321 Ashford Rd, Chiang Mai": b"321 Ashford Rd, Chiang Mai",
    b"654 Greenfield Rd, Chiang Mai": b"654 Greenfield Rd, Chiang Mai",
    b"321 Harborview Rd, Chiang Mai": b"321 Harborview Rd, Chiang Mai",
    b"101 Sunrise St, Chiang Mai": b"101 Sunrise St, Chiang Mai",
    b"202 Union St, Chiang Mai": b"202 Union St, Chiang Mai",
    b"ChIJSYNTHETIC00000000000000001": b"ChIJSYNTHETIC00000000000000001",
    b"ChIJSYNTHETIC00000000000000002": b"ChIJSYNTHETIC00000000000000002",
    b"ChIJSYNTHETIC00000000000000003": b"ChIJSYNTHETIC00000000000000003",
    b"ChIJSYNTHETIC00000000000000004": b"ChIJSYNTHETIC00000000000000004",
    b"ChIJSYNTHETIC00000000000000005": b"ChIJSYNTHETIC00000000000000005",
    b"ChIJSYNTHETIC00000000000000006": b"ChIJSYNTHETIC00000000000000006",
    b"ChIJSYNTHETIC00000000000000007": b"ChIJSYNTHETIC00000000000000007",
    b"ChIJSYNTHETIC00000000000000008": b"ChIJSYNTHETIC00000000000000008",
    b"ChIJSYNTHETIC00000000000000009": b"ChIJSYNTHETIC00000000000000009",
    b"ChIJSYNTHETIC00000000000000010": b"ChIJSYNTHETIC00000000000000010",
    b"ChIJSYNTHETIC00000000000000011": b"ChIJSYNTHETIC00000000000000011",
    b"ChIJSYNTHETIC00000000000000012": b"ChIJSYNTHETIC00000000000000012",
    b"ChIJSYNTHETIC00000000000000013": b"ChIJSYNTHETIC00000000000000013",
    b"ChIJSYNTHETIC00000000000000014": b"ChIJSYNTHETIC00000000000000014",
    b"ChIJSYNTHETIC00000000000000015": b"ChIJSYNTHETIC00000000000000015",
    b"ChIJSYNTHETIC00000000000000016": b"ChIJSYNTHETIC00000000000000016",
    b"ChIJSYNTHETIC00000000000000017": b"ChIJSYNTHETIC00000000000000017",
    b"ChIJSYNTHETIC00000000000000018": b"ChIJSYNTHETIC00000000000000018",
    b"ChIJSYNTHETIC00000000000000019": b"ChIJSYNTHETIC00000000000000019",
    b"ChIJSYNTHETIC00000000000000020": b"ChIJSYNTHETIC00000000000000020",
    b"ChIJSYNTHETIC00000000000000021": b"ChIJSYNTHETIC00000000000000021",
    b"ChIJSYNTHETIC00000000000000022": b"ChIJSYNTHETIC00000000000000022",
    b"+66 53 000 001": b"+66 53 000 001",
    b"77/5 Dockyard Lane, Bangkok 10160, Thailand": b"77/5 Dockyard Lane, Bangkok 10160, Thailand",
    b"+66 2 555 0101": b"+66 2 555 0101",
    b"+66 2 555 0102": b"+66 2 555 0102",
    b"+66 53 000 002": b"+66 53 000 002",
    b"+66 53 000 003": b"+66 53 000 003",
    b"+66 53 000 004": b"+66 53 000 004",
    b"+66 53 000 005": b"+66 53 000 005",
    b"+66 53 000 006": b"+66 53 000 006",
    b"+66 53 000 007": b"+66 53 000 007",
    b"+66 53 000 008": b"+66 53 000 008",
    b"+66 53 000 009": b"+66 53 000 009",
    b"+66 53 000 010": b"+66 53 000 010",
    b"+66 53 000 011": b"+66 53 000 011",
    b"+66 53 000 012": b"+66 53 000 012",
    b"+66 53 000 013": b"+66 53 000 013",
    b"+66 53 000 014": b"+66 53 000 014",
    b"+66 53 000 015": b"+66 53 000 015",
    b"+66 53 000 016": b"+66 53 000 016",
    b"192.0.2.1": b"192.0.2.1",
    b"iker.goni@users.noreply.github.com": b"iker.goni@users.noreply.github.com",
    b"/home/user/project": b"/home/user/project",
    b"/Users/demo/": b"/Users/demo/",
    b"Maplewood": b"Maplewood",
    b"Birchwood": b"Birchwood",
    b"Lakeshore": b"Lakeshore",
    b"Hillcrest": b"Hillcrest",
    b"Dockside": b"Dockside",
    b"Cedarbrook": b"Cedarbrook",
    b"Fernhill": b"Fernhill",
    b"Stonebridge": b"Stonebridge",
    b"Kingsway": b"Kingsway",
    b"Northhill": b"Northhill",
    b"Westgate": b"Westgate",
    b"Eastgate": b"Eastgate",
    b"Market District": b"Market District",
    b"Southgate": b"Southgate",
    b"social-media steps": b"social-media steps",
}

_ORDERED_KEYS = sorted(raw_replacements.keys(), key=len, reverse=True)


def _replace_all(data):
    for old in _ORDERED_KEYS:
        if old in data:
            data = data.replace(old, raw_replacements[old])
    return data


def blob_callback(blob, metadata):
    blob.data = _replace_all(blob.data)


def commit_callback(commit, metadata):
    commit.message = _replace_all(commit.message)
    if commit.author_email == b"iker.goni@users.noreply.github.com":
        commit.author_name = b"Iker Go\xc3\xb1i"
        commit.author_email = b"iker.goni@users.noreply.github.com"
    if commit.committer_email == b"iker.goni@users.noreply.github.com":
        commit.committer_name = b"Iker Go\xc3\xb1i"
        commit.committer_email = b"iker.goni@users.noreply.github.com"


def tag_callback(tag, metadata):
    tag.message = _replace_all(tag.message)
