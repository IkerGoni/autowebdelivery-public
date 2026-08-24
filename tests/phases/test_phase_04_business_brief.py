import tempfile
import json
from pathlib import Path

from pipeline.json_io import read_json, write_json
from packages.phases.phase_04_business_brief import (
    BLOCKED_REASON,
    detect_recipient_channel,
    route_briefs,
    run_phase_04,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "phase_04_business_brief_generation"


def _load_fixture(name: str):
    return read_json(str(FIXTURE_DIR / name))


class TestRecipientRouting:
    def test_detect_recipient_channel_social_facebook(self):
        lead = _load_fixture("input/selected_lead_social_only.json")[0]
        recipient = detect_recipient_channel(lead)
        assert recipient["recipient_channel"] == "facebook_message"
        assert recipient["recipient_source"] == "social_profile"
        assert recipient["recipient_confidence"] == "inferred"

    def test_route_briefs_unknown_to_blocked(self):
        preview_ready, blocked = route_briefs([
            {
                "business_slug": "unknown-brief",
                "brief_path": "runs/fixture_001/04_briefs/unknown-brief",
                "recipient_channel": "unknown",
                "manual_override": False,
                "manual_override_reason": "",
            }
        ])
        assert preview_ready == []
        assert blocked == [
            {
                "business_slug": "unknown-brief",
                "brief_path": "runs/fixture_001/04_briefs/unknown-brief",
                "recipient_channel": "unknown",
                "blocked_reason": BLOCKED_REASON,
            }
        ]


class TestRunPhase04:
    def test_run_phase_04_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id
            (run_dir / "config").mkdir(parents=True, exist_ok=True)
            (run_dir / "03_scoring").mkdir(parents=True, exist_ok=True)

            config = {
                "run_id": run_id,
                "niche": "dentists",
                "area": "Chiang Mai",
                "country": "Thailand",
                "language": "English",
                "style_preset": None,
                "price_offer": "$299 one-time setup",
            }
            write_json(str(run_dir / "config" / "input_config.json"), config)

            selected = []
            for fixture_name in [
                "input/selected_lead_complete.json",
                "input/selected_lead_missing_phone.json",
                "input/selected_lead_missing_hours.json",
                "input/selected_lead_social_only.json",
                "input/selected_lead_unknown_recipient_channel.json",
            ]:
                selected.extend(_load_fixture(fixture_name))
            write_json(str(run_dir / "03_scoring" / "selected_for_preview.json"), selected)

            result = run_phase_04(run_id, str(root))
            assert result["status"] == "done"

            briefs_index = read_json(str(run_dir / "04_briefs" / "briefs_index.json"))
            preview_ready = read_json(str(run_dir / "04_briefs" / "preview_ready_briefs.json"))
            blocked = read_json(str(run_dir / "04_briefs" / "blocked_no_recipient_channel.json"))

            expected_index = _load_fixture("expected/briefs_index_expected.json")
            expected_preview_ready = _load_fixture("expected/preview_ready_briefs_expected.json")
            expected_blocked = _load_fixture("expected/blocked_no_recipient_channel_expected.json")

            assert briefs_index == expected_index
            assert preview_ready == expected_preview_ready
            assert blocked == expected_blocked

            facts_path = run_dir / "04_briefs" / "quiet-canal-dental-missing-phone" / "FACTS.md"
            missing_path = run_dir / "04_briefs" / "quiet-canal-dental-missing-phone" / "MISSING_DATA.md"
            recipient_path = run_dir / "04_briefs" / "riverfront-dental-lab-social-only" / "recipient_channel.json"
            prompt_path = run_dir / "04_briefs" / "hilltop-dental-corner-unknown-recipient" / "GENERATION_PROMPT.md"

            assert facts_path.exists()
            assert missing_path.exists()
            assert recipient_path.exists()
            assert prompt_path.exists()

            facts = facts_path.read_text(encoding="utf-8")
            missing = missing_path.read_text(encoding="utf-8")
            prompt = prompt_path.read_text(encoding="utf-8")
            recipient = read_json(str(recipient_path))

            assert "- business_name: Quiet Canal Dental" in facts
            assert "- recipient_channel: unknown" in facts
            assert "- phone" in missing
            assert "- hours" in prompt
            assert recipient["recipient_channel"] == "facebook_message"

    def test_run_phase_04_blocked_when_inputs_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_04("missing_run", tmp)
            assert result["status"] == "blocked"
            assert "RunConfig" in result["missing_fields"]
            assert "selected_for_preview[]" in result["missing_fields"]


# ---------------------------------------------------------------------------
# VNEXT-01 — feature-flag tests for the optional business_profile.json output.
# These tests opt in (or out) of the flag inside the function only, leaving
# the default config unchanged.
# ---------------------------------------------------------------------------

def _seed_run(root: Path, run_id: str, *, flag: bool | None = None) -> str:
    """Set up a Phase 04 run with the 5 standard fixtures and return the
    absolute root path. If `flag` is not None, the config will include
    `use_business_profile_contract=<flag>`. The flag is NEVER set in the
    default config — callers must opt in explicitly per-call."""
    run_dir = root / "runs" / run_id
    (run_dir / "config").mkdir(parents=True, exist_ok=True)
    (run_dir / "03_scoring").mkdir(parents=True, exist_ok=True)

    config = {
        "run_id": run_id,
        "niche": "dentists",
        "area": "Chiang Mai",
        "country": "Thailand",
        "language": "English",
        "style_preset": None,
        "price_offer": "$299 one-time setup",
    }
    if flag is not None:
        config["use_business_profile_contract"] = bool(flag)
    write_json(str(run_dir / "config" / "input_config.json"), config)

    selected = []
    for fixture_name in [
        "input/selected_lead_complete.json",
        "input/selected_lead_missing_phone.json",
        "input/selected_lead_missing_hours.json",
        "input/selected_lead_social_only.json",
        "input/selected_lead_unknown_recipient_channel.json",
    ]:
        selected.extend(_load_fixture(fixture_name))
    write_json(str(run_dir / "03_scoring" / "selected_for_preview.json"), selected)

    return str(root)


class TestBusinessProfileContractFlag:
    def test_flag_off_does_not_write_business_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seed_run(Path(tmp), "fixture_001", flag=False)
            result = run_phase_04("fixture_001", root)
            assert result["status"] == "done"

            briefs_dir = Path(root) / "runs" / "fixture_001" / "04_briefs"
            # No business_profile.json anywhere under the briefs dir
            profiles = list(briefs_dir.rglob("business_profile.json"))
            assert profiles == [], f"unexpected business_profile.json files: {profiles}"
            # And it must not appear in outputs_created either
            assert not any(
                "business_profile.json" in path
                for path in result.get("outputs_created", [])
            )

    def test_flag_on_writes_business_profile_for_each_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seed_run(Path(tmp), "fixture_001", flag=True)
            result = run_phase_04("fixture_001", root)
            assert result["status"] == "done"

            briefs_dir = Path(root) / "runs" / "fixture_001" / "04_briefs"

            # The flag was set ONLY in this function — verify the
            # use_business_profile_contract key survived the round trip.
            config = read_json(
                str(Path(root) / "runs" / "fixture_001" / "config" / "input_config.json")
            )
            assert config.get("use_business_profile_contract") is True

            # Every business in the briefs_index must have a profile file
            briefs_index = read_json(str(briefs_dir / "briefs_index.json"))
            assert len(briefs_index) == 5
            for row in briefs_index:
                profile_path = (
                    briefs_dir / row["business_slug"] / "business_profile.json"
                )
                assert profile_path.exists(), f"missing {profile_path}"
                profile = read_json(str(profile_path))
                assert profile["schema_version"] == "1.1.0"
                assert profile["run_id"] == "fixture_001"
                assert profile["business_slug"] == row["business_slug"]

            # outputs_created surfaces every profile
            created = result.get("outputs_created", [])
            for row in briefs_index:
                expected = (
                    f"runs/fixture_001/04_briefs/"
                    f"{row['business_slug']}/business_profile.json"
                )
                assert expected in created, f"missing in outputs_created: {expected}"

    def test_flag_off_preserves_legacy_outputs_byte_identical(self):
        """Running with the flag on must not mutate FACTS.md or
        BUSINESS_BRIEF.md compared to a flag-off run with the same inputs."""
        def _snapshot_legacy_files(root: Path) -> dict[str, dict[str, bytes]]:
            briefs_dir = root / "runs" / "fixture_001" / "04_briefs"
            snapshot: dict[str, dict[str, bytes]] = {}
            for business_dir in sorted(p for p in briefs_dir.iterdir() if p.is_dir()):
                files = {}
                for name in ("FACTS.md", "BUSINESS_BRIEF.md"):
                    p = business_dir / name
                    files[name] = p.read_bytes()
                snapshot[business_dir.name] = files
            return snapshot

        with tempfile.TemporaryDirectory() as tmp:
            root_off = _seed_run(Path(tmp) / "off", "fixture_001", flag=False)
            run_phase_04("fixture_001", root_off)
            off_snapshot = _snapshot_legacy_files(Path(root_off))

        with tempfile.TemporaryDirectory() as tmp:
            root_on = _seed_run(Path(tmp) / "on", "fixture_001", flag=True)
            run_phase_04("fixture_001", root_on)
            on_snapshot = _snapshot_legacy_files(Path(root_on))

        assert set(off_snapshot.keys()) == set(on_snapshot.keys())
        for slug in off_snapshot:
            for name in ("FACTS.md", "BUSINESS_BRIEF.md"):
                assert off_snapshot[slug][name] == on_snapshot[slug][name], (
                    f"legacy output drift in {slug}/{name} when flag is ON"
                )

class TestMarketProfileContractFlag:
    def test_flag_off_does_not_write_market_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_mp_off"
            _seed_run(root, run_id, flag=False) # mock call
            
            result = run_phase_04(run_id, str(root))
            assert result["status"] == "done"
            
            briefs_dir = root / "runs" / run_id / "04_briefs"
            profiles = list(briefs_dir.rglob("market_profile.json"))
            assert profiles == []
            assert not any("market_profile.json" in p for p in result.get("outputs_created", []))

    def test_flag_on_writes_market_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_mp_on"
            
            _seed_run(root, run_id, flag=False)
            cfg_path = root / "runs" / run_id / "config" / "input_config.json"
            cfg = read_json(str(cfg_path))
            cfg["use_market_profile_contract"] = True
            write_json(str(cfg_path), cfg)
            
            result = run_phase_04(run_id, str(root))
            assert result["status"] == "done"
            
            # Should have market_profile.json for each business
            scored = [p for p in result["outputs_created"] if "market_profile.json" in p]
            assert len(scored) == 5
            
            for path in scored:
                full_path = root / path
                assert full_path.exists()
                profile = json.loads(full_path.read_text())
                assert profile["schema_version"] == "1.1.0"
