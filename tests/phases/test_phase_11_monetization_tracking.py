import tempfile
from pathlib import Path

from pipeline.json_io import read_json, write_json
from packages.phases.phase_11_monetization_tracking import (
    DEFAULT_MVP_STOP_THRESHOLD,
    PROCEED_DECISION,
    ZERO_DEMAND_DECISION,
    run_phase_11,
    summarize_monetization,
    write_objections_log,
)


class TestPhase11MonetizationTracking:
    def test_summarize_monetization_stop_or_pivot_at_threshold_with_zero_demand(self):
        sent_log = [{"record_id": f"sent_{i:03d}"} for i in range(DEFAULT_MVP_STOP_THRESHOLD)]
        summary = summarize_monetization(sent_log, [], mvp_stop_threshold=DEFAULT_MVP_STOP_THRESHOLD)

        assert summary["total_sent"] == DEFAULT_MVP_STOP_THRESHOLD
        assert summary["reply_count"] == 0
        assert summary["serious_interest_count"] == 0
        assert summary["should_stop_or_pivot"] is True
        assert summary["decision"] == ZERO_DEMAND_DECISION

    def test_summarize_monetization_continue_when_reply_exists(self):
        sent_log = [{"record_id": f"sent_{i:03d}"} for i in range(20)]
        manual_updates = [
            {
                "run_id": "fixture_001",
                "business_slug": "biz-1",
                "event_type": "reply",
                "notes": "Asked for pricing",
            }
        ]

        summary = summarize_monetization(sent_log, manual_updates, mvp_stop_threshold=20)

        assert summary["reply_count"] == 1
        assert summary["should_stop_or_pivot"] is False
        assert summary["decision"] == PROCEED_DECISION

    def test_summarize_monetization_counts_unique_sent_and_legacy_status(self):
        sent_log = [
            {"record_id": "sent_001", "business_slug": "biz-1", "sent_status": "sent", "niche": "dental"},
            {"record_id": "sent_001_dup", "business_slug": "biz-1", "sent_status": "sent", "niche": "dental"},
            {"record_id": "sent_002", "business_slug": "biz-2", "niche": "salon"},
            {"record_id": "sent_003", "business_slug": "biz-3", "sent_status": "skipped", "niche": "fitness"},
            {"record_id": "sent_004", "business_slug": "biz-4", "sent_status": "failed", "niche": "legal"},
        ]
        manual_updates = [
            {"sent_record_id": "sent_001", "business_slug": "biz-1", "event_type": "reply"},
            {"sent_record_id": "sent_003", "business_slug": "biz-3", "event_type": "reply"},
        ]

        summary = summarize_monetization(sent_log, manual_updates, mvp_stop_threshold=20)

        assert summary["total_sent"] == 2
        assert summary["segment_analytics"]["by_niche"]["dental"]["total_sent"] == 1
        assert summary["segment_analytics"]["by_niche"]["salon"]["total_sent"] == 1
        assert "fitness" not in summary["segment_analytics"]["by_niche"]
        assert "legal" not in summary["segment_analytics"]["by_niche"]
        assert len(summary["lead_status_ledger"]) == 2

    def test_summarize_monetization_lead_status_ledger_lifecycle_events(self):
        sent_log = [
            {"record_id": "sent_001", "business_slug": "biz-1", "sent_status": "sent"},
            {"record_id": "sent_002", "business_slug": "biz-2", "sent_status": "sent"},
            {"record_id": "sent_003", "business_slug": "biz-3", "sent_status": "sent"},
        ]
        manual_updates = [
            {"sent_record_id": "sent_001", "business_slug": "biz-1", "event_type": "opt_out", "notes": "No more email"},
            {"sent_record_id": "sent_002", "business_slug": "biz-2", "event_type": "removal_requested"},
            {"sent_record_id": "sent_003", "business_slug": "biz-3", "event_type": "removed"},
        ]

        summary = summarize_monetization(sent_log, manual_updates, mvp_stop_threshold=20)
        ledger = {row["business_slug"]: row for row in summary["lead_status_ledger"]}

        assert ledger["biz-1"]["lead_status"] == "opted_out"
        assert ledger["biz-1"]["opted_out"] is True
        assert ledger["biz-2"]["lead_status"] == "removal_requested"
        assert ledger["biz-2"]["removal_requested"] is True
        assert ledger["biz-3"]["lead_status"] == "removed"
        assert ledger["biz-3"]["removed"] is True

    def test_summarize_monetization_segments_by_niche_area_channel_template_and_offer(self):
        sent_log = [
            {
                "record_id": "sent_001",
                "business_slug": "dental-a",
                "niche": "dental",
                "area": "Madrid",
                "recipient_channel": "email",
                "template_family": "clinical_trust",
                "offer_type": "setup_only",
                "offer_price": "299",
                "currency": "EUR",
                "pricing_market": "Madrid, Spain",
            },
            {
                "record_id": "sent_002",
                "business_slug": "salon-a",
                "niche": "salon",
                "area": "Barcelona",
                "recipient_channel": "instagram_dm",
                "template_family": "warm_editorial",
                "offer_type": "monthly",
                "offer_price": "99",
                "currency": "EUR",
                "pricing_market": "Barcelona, Spain",
            },
            {
                "record_id": "sent_003",
                "business_slug": "dental-b",
                "niche": "dental",
                "area": "Madrid",
                "recipient_channel": "email",
                "template_family": "clinical_trust",
                "offer_type": "setup_only",
                "offer_price": "299",
                "currency": "EUR",
                "pricing_market": "Madrid, Spain",
            },
        ]
        manual_updates = [
            {
                "sent_record_id": "sent_001",
                "business_slug": "dental-a",
                "event_type": "reply",
            },
            {
                "sent_record_id": "sent_002",
                "business_slug": "salon-a",
                "event_type": "paid_conversion",
            },
        ]

        summary = summarize_monetization(sent_log, manual_updates, mvp_stop_threshold=20)

        analytics = summary["segment_analytics"]
        assert analytics["by_niche"]["dental"]["total_sent"] == 2
        assert analytics["by_niche"]["dental"]["reply_count"] == 1
        assert analytics["by_niche"]["salon"]["paid_conversion_count"] == 1
        assert analytics["by_area"]["Madrid"]["total_sent"] == 2
        assert analytics["by_recipient_channel"]["email"]["reply_rate"] == 0.5
        assert analytics["by_template_family"]["warm_editorial"]["paid_conversion_rate"] == 1.0
        offer_key = "setup_only|299|EUR|Madrid, Spain"
        assert analytics["by_offer"][offer_key]["total_sent"] == 2

    def test_write_objections_log(self):
        objections = [
            {
                "run_id": "fixture_001",
                "event_id": "evt_001",
                "business_slug": "biz-1",
                "sent_record_id": "sent_001",
                "event_type": "objection",
                "objection": "too_expensive",
                "notes": "Need lower price",
                "occurred_at": "2025-01-01T00:00:00Z",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "objections_log.csv"
            write_objections_log(objections, output_path)

            assert output_path.exists()
            content = output_path.read_text(encoding="utf-8")
            assert "objection" in content
            assert "too_expensive" in content

    def test_run_phase_11_blocked_when_sent_log_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_phase_11("missing_run", tmp)
            assert result["status"] == "blocked"
            assert "sent_log.json" in result["missing_fields"]

    def test_run_phase_11_complete_with_stop_or_pivot_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "config").mkdir(parents=True, exist_ok=True)
            write_json(str(run_dir / "config" / "input_config.json"), {
                "price_offer": "$299 setup",
                "mvp_stop_threshold": 20,
            })

            sent_dir = run_dir / "10_sent"
            sent_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                str(sent_dir / "sent_log.json"),
                [{"record_id": f"sent_{i:03d}", "business_slug": f"biz-{i:03d}"} for i in range(20)],
            )

            results_dir = run_dir / "11_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(results_dir / "manual_updates.json"), [
                {
                    "run_id": run_id,
                    "business_slug": "biz-001",
                    "business_name": "Biz 001",
                    "niche": "dentist",
                    "area": "Madrid",
                    "country": "Spain",
                    "template_family": "clinical_trust",
                    "template_variant": "single_page_preview",
                    "stitch_project_id": "stitch_123",
                    "offer_type": "setup_only",
                    "offer_price": "299",
                    "currency": "EUR",
                    "pricing_market": "Madrid, Spain",
                    "event_type": "objection",
                    "objection": "no_budget",
                    "notes": "Not this quarter",
                }
            ])

            result = run_phase_11(run_id, str(root))

            assert result["status"] == "done"
            assert result["records_processed"] == 20
            assert result["records_created"] == 1
            assert "Decision: stop_or_pivot" in result["decisions"]

            assert (results_dir / "mvp_results.md").exists()
            assert (results_dir / "objections_log.csv").exists()
            assert (results_dir / "monetization_events.json").exists()
            assert (results_dir / "monetization_segment_analytics.json").exists()
            assert (results_dir / "lead_status_ledger.json").exists()
            assert (results_dir / "lead_status_ledger.csv").exists()
            assert (results_dir / "next_iteration_decision.md").exists()
            assert (results_dir / "result.json").exists()

            events = read_json(str(results_dir / "monetization_events.json"))
            assert len(events) == 1
            assert events[0]["objection"] == "no_budget"
            assert events[0]["business_name"] == "Biz 001"
            assert events[0]["niche"] == "dentist"
            assert events[0]["area"] == "Madrid"
            assert events[0]["country"] == "Spain"
            assert events[0]["template_family"] == "clinical_trust"
            assert events[0]["template_variant"] == "single_page_preview"
            assert events[0]["stitch_project_id"] == "stitch_123"
            assert events[0]["offer_price"] == "299"
            assert events[0]["currency"] == "EUR"
            assert events[0]["pricing_market"] == "Madrid, Spain"

            segment_analytics = read_json(str(results_dir / "monetization_segment_analytics.json"))
            assert segment_analytics["by_niche"]["unknown"]["total_sent"] == 20
            assert segment_analytics["by_niche"]["dentist"]["objection_count"] == 1

            mvp_results = (results_dir / "mvp_results.md").read_text(encoding="utf-8")
            assert "Decision: stop_or_pivot" in mvp_results
            assert "Objections Logged: 1" in mvp_results

    def test_run_phase_11_complete_with_reply_continues_testing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "fixture_001"
            run_dir = root / "runs" / run_id

            (run_dir / "config").mkdir(parents=True, exist_ok=True)
            write_json(str(run_dir / "config" / "input_config.json"), {
                "price_offer": "$299 setup",
                "mvp_stop_threshold": 20,
            })

            sent_dir = run_dir / "10_sent"
            sent_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                str(sent_dir / "sent_log.json"),
                [{"record_id": f"sent_{i:03d}", "business_slug": f"biz-{i:03d}"} for i in range(20)],
            )

            results_dir = run_dir / "11_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            write_json(str(results_dir / "manual_updates.json"), [
                {
                    "run_id": run_id,
                    "business_slug": "biz-001",
                    "business_name": "Biz 001",
                    "niche": "dentist",
                    "area": "Madrid",
                    "country": "Spain",
                    "template_family": "clinical_trust",
                    "template_variant": "single_page_preview",
                    "stitch_project_id": "stitch_123",
                    "offer_type": "setup_only",
                    "offer_price": "299",
                    "currency": "EUR",
                    "pricing_market": "Madrid, Spain",
                    "event_type": "reply",
                    "notes": "Interested in call",
                },
                {
                    "run_id": run_id,
                    "business_slug": "biz-001",
                    "business_name": "Biz 001",
                    "niche": "dentist",
                    "area": "Madrid",
                    "country": "Spain",
                    "template_family": "clinical_trust",
                    "template_variant": "single_page_preview",
                    "stitch_project_id": "stitch_123",
                    "offer_type": "setup_only",
                    "offer_price": "299",
                    "currency": "EUR",
                    "pricing_market": "Madrid, Spain",
                    "event_type": "meeting",
                    "notes": "Booked Friday",
                },
                {
                    "run_id": run_id,
                    "business_slug": "biz-001",
                    "business_name": "Biz 001",
                    "niche": "dentist",
                    "area": "Madrid",
                    "country": "Spain",
                    "template_family": "clinical_trust",
                    "template_variant": "single_page_preview",
                    "stitch_project_id": "stitch_123",
                    "offer_type": "setup_only",
                    "offer_price": "299",
                    "currency": "EUR",
                    "pricing_market": "Madrid, Spain",
                    "event_type": "paid_conversion",
                    "notes": "Paid deposit",
                },
            ])

            result = run_phase_11(run_id, str(root))

            assert result["status"] == "done"
            assert "Decision: continue_testing" in result["decisions"]

            events = read_json(str(results_dir / "monetization_events.json"))
            assert len(events) == 3
            assert sum(1 for event in events if event["reply_received"]) == 3
            assert sum(1 for event in events if event["meeting_booked"]) == 1
            assert sum(1 for event in events if event["paid_conversion"]) == 1
            assert all(event["niche"] == "dentist" for event in events)
            assert all(event["area"] == "Madrid" for event in events)
            assert all(event["country"] == "Spain" for event in events)
            assert all(event["template_family"] == "clinical_trust" for event in events)
            assert all(event["template_variant"] == "single_page_preview" for event in events)
            assert all(event["stitch_project_id"] == "stitch_123" for event in events)
            assert all(event["offer_price"] == "299" for event in events)
            assert all(event["currency"] == "EUR" for event in events)
            assert all(event["pricing_market"] == "Madrid, Spain" for event in events)

            mvp_results = (results_dir / "mvp_results.md").read_text(encoding="utf-8")
            assert "Decision: continue_testing" in mvp_results
            assert "Paid Conversions: 1" in mvp_results
