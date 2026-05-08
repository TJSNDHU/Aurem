"""
Tests for ORA Command Center parser + executor wiring.
Run: pytest backend/tests/test_ora_command_center.py -v
"""
import pytest
from services.ora_command_center import parse_command


class TestParser:
    def test_help_variants(self):
        for t in ["help", "Commands", "/help", "/start", "?"]:
            assert parse_command(t)["intent"] == "HELP"

    def test_scout_city_industry(self):
        p = parse_command("Scout Toronto auto shops")
        assert p["intent"] == "SCOUT"
        assert p["params"]["city"] == "Toronto"
        assert "auto" in p["params"]["industry"]

    def test_scout_freeform(self):
        p = parse_command("Scout some niche thing")
        assert p["intent"] == "SCOUT"
        assert "query" in p["params"] or "city" in p["params"]

    def test_blast_one(self):
        p = parse_command("Blast Damons Landscaping")
        assert p["intent"] == "BLAST_ONE"
        assert p["params"]["business_name"] == "Damons Landscaping"

    def test_blast_bulk(self):
        p = parse_command("Blast all Toronto leads")
        assert p["intent"] == "BLAST_BULK"
        assert p["params"]["city"] == "Toronto"

    def test_stats(self):
        assert parse_command("Show campaign stats")["intent"] == "STATS"

    def test_lead_count(self):
        p = parse_command("How many leads today")
        assert p["intent"] == "LEAD_COUNT"

    def test_replies(self):
        assert parse_command("Who replied")["intent"] == "REPLIES"

    def test_pipeline(self):
        assert parse_command("Show pipeline")["intent"] == "PIPELINE"

    def test_website_build(self):
        p = parse_command("Build website for damons-landscaping")
        assert p["intent"] == "WEBSITE_BUILD"
        assert p["params"]["slug"] == "damons-landscaping"

    def test_website_send(self):
        p = parse_command("Send website to Damons Landscaping")
        assert p["intent"] == "WEBSITE_SEND"
        assert "damons" in p["params"]["business_name"].lower()

    def test_pause_resume(self):
        assert parse_command("Pause campaigns")["intent"] == "PAUSE"
        assert parse_command("Resume campaigns")["intent"] == "RESUME"

    def test_verify_simple(self):
        p = parse_command("Verify Damons Landscaping")
        assert p["intent"] == "VERIFY"
        assert "damons" in p["params"]["business_name"].lower()

    def test_verify_with_city(self):
        p = parse_command("Verify Tim Hortons in Toronto")
        assert p["intent"] == "VERIFY"
        assert "tim hortons" in p["params"]["business_name"].lower()
        assert p["params"]["city"].lower() == "toronto"

    def test_unknown(self):
        assert parse_command("asdfghjkl")["intent"] == "UNKNOWN"
        assert parse_command("")["intent"] == "UNKNOWN"

    def test_case_insensitive(self):
        assert parse_command("SCOUT toronto salons")["intent"] == "SCOUT"
        assert parse_command("show CAMPAIGN stats")["intent"] == "STATS"


def test_executor_help_does_not_need_db():
    import asyncio
    from services.ora_command_center import execute_command
    result = asyncio.run(execute_command(None, "help", channel="test", user="tester"))
    assert result["ok"] is True
    assert result["intent"] == "HELP"
    assert "Scout" in result["reply"]
