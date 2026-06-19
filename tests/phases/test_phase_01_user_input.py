"""Tests for Phase 01 User Input per pipeline_data_contract.md."""

import pytest
import tempfile
from pathlib import Path

from pipeline.json_io import read_json
from packages.phases.phase_01_user_input import (
    run,
    validate_config,
    make_run_config,
    make_query_plan,
)


class TestValidateConfig:
    def test_valid_minimal_config(self):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        assert validate_config(config) == []

    def test_valid_custom_thresholds(self):
        config = {
            "niche": "restaurants",
            "area": "Bangkok",
            "country": "Thailand",
            "max_raw_results": 50,
            "max_preview_sites": 10,
            "minimum_rating": 4.5,
            "minimum_reviews": 100,
            "price_offer": "$199 one-time",
        }
        assert validate_config(config) == []

    def test_missing_area(self):
        config = {
            "niche": "dentists",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299",
        }
        errors = validate_config(config)
        assert "area" in errors

    def test_preview_gt_raw_results(self):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 10,
            "max_preview_sites": 50,
            "price_offer": "$299",
        }
        errors = validate_config(config)
        assert any("max_preview_sites" in e for e in errors)

    def test_invalid_rating_threshold(self):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "minimum_rating": 6.0,
            "price_offer": "$299",
        }
        errors = validate_config(config)
        assert any("minimum_rating" in e for e in errors)

    def test_missing_multiple_fields(self):
        config = {
            "niche": "dentists",
        }
        errors = validate_config(config)
        assert "area" in errors
        assert "country" in errors
        assert "max_raw_results" in errors
        assert "max_preview_sites" in errors
        assert "price_offer" in errors


class TestMakeRunConfig:
    def test_creates_with_defaults(self):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299",
        }
        run_config = make_run_config(config, "test_run")
        assert run_config.run_id == "test_run"
        assert run_config.niche == "dentists"
        assert run_config.area == "Chiang Mai"
        assert run_config.language == "English"
        assert run_config.minimum_rating == 4.3
        assert run_config.mvp_stop_threshold == 20

    def test_custom_thresholds(self):
        config = {
            "niche": "restaurants",
            "area": "Bangkok",
            "country": "Thailand",
            "max_raw_results": 50,
            "max_preview_sites": 10,
            "minimum_rating": 4.5,
            "minimum_reviews": 50,
            "price_offer": "$199",
            "mvp_stop_threshold": 15,
        }
        run_config = make_run_config(config, "custom_run")
        assert run_config.minimum_rating == 4.5
        assert run_config.minimum_reviews == 50
        assert run_config.mvp_stop_threshold == 15


class TestMakeQueryPlan:
    def test_creates_query_plan(self):
        from pipeline.contracts import RunConfig
        run_config = RunConfig(
            run_id="test_run",
            niche="dentists",
            area="Chiang Mai",
            country="Thailand",
            price_offer="$299",
        )
        qp = make_query_plan(run_config)
        assert qp.run_id == "test_run"
        assert len(qp.queries) == 1
        assert qp.queries[0]["search_text"] == "dentists Chiang Mai"
        assert qp.queries[0]["max_results"] == 50


class TestPhase01Run:
    @pytest.fixture
    def workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_run_with_valid_config(self, workspace):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
        }
        result = run("test_run_001", workspace, config)
        assert result["status"] == "done"
        assert result["run_id"] == "test_run_001"
        assert "config/input_config.json" in result["outputs_created"]

        # Check artifacts exist
        assert Path(workspace, "runs", "test_run_001", "config", "input_config.json").exists()
        assert Path(workspace, "runs", "test_run_001", "01_input", "query_plan.json").exists()
        assert Path(workspace, "runs", "test_run_001", "01_input", "result.json").exists()

    def test_run_with_missing_area(self, workspace):
        config = {
            "niche": "dentists",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299",
        }
        result = run("test_run_002", workspace, config)
        assert result["status"] == "blocked"
        assert "area" in result["missing_fields"]

    def test_run_with_preview_gt_raw(self, workspace):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 5,
            "max_preview_sites": 50,
            "price_offer": "$299",
        }
        result = run("test_run_003", workspace, config)
        assert result["status"] == "blocked"

    def test_artifact_contents(self, workspace):
        config = {
            "niche": "dentists",
            "area": "Chiang Mai",
            "country": "Thailand",
            "max_raw_results": 100,
            "max_preview_sites": 5,
            "price_offer": "$299 setup",
            "mvp_stop_threshold": 20,
        }
        run("test_run_004", workspace, config)

        # Check RunConfig artifact
        input_config = read_json(f"{workspace}/runs/test_run_004/config/input_config.json")
        assert input_config["niche"] == "dentists"
        assert input_config["area"] == "Chiang Mai"
        assert input_config["mvp_stop_threshold"] == 20

        # Check QueryPlan artifact
        query_plan = read_json(f"{workspace}/runs/test_run_004/01_input/query_plan.json")
        assert query_plan["run_id"] == "test_run_004"
        assert len(query_plan["queries"]) == 1