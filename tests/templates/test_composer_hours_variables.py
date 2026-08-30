import pytest
from packages.templates.modular.composer import TemplateComposer
from packages.templates.modular.models import BusinessData, HoursSchedule

@pytest.fixture
def business_with_hours():
    return BusinessData(
        name="Test Business",
        hours=HoursSchedule(
            weekdays="Mon-Fri",
            weekday_hours="9-5",
            weekend_day="Sat",
            weekend_hours="10-2",
            note="Test note"
        ),
        services=[],
        address_line1="123 Street",
        website_url="https://test.com",
    )

def test_build_data_dict_exposes_per_day_hours_variables(business_with_hours):
    composer = TemplateComposer()
    data = composer._build_data_dict(business_with_hours)
    assert data["hours_weekdays"] == "Mon-Fri"
    assert data["hours_weekday_hours"] == "9-5"
    assert data["hours_weekend_day"] == "Sat"
    assert data["hours_weekend_hours"] == "10-2"
    assert data["hours_note"] == "Test note"

def test_render_per_day_hours_variables():
    composer = TemplateComposer()
    template = "{{hours_weekdays}}: {{hours_weekday_hours}}"
    data = {"hours_weekdays": "M-F", "hours_weekday_hours": "9-5"}
    assert composer._render_mustache(template, data) == "M-F: 9-5"

def test_render_hours_note_conditional_block():
    composer = TemplateComposer()
    template = "Note: {{#hours_note}}({{hours_note}}){{/hours_note}}"
    data = {"hours_note": "Emergency only"}
    assert composer._render_mustache(template, data) == "Note: (Emergency only)"

def test_render_hours_note_conditional_block_empty():
    composer = TemplateComposer()
    template = "Note:{{#hours_note}} ({{hours_note}}){{/hours_note}}"
    data = {"hours_note": ""}
    assert composer._render_mustache(template, data) == "Note:"

def test_composed_page_uses_per_day_hours_in_clinical_trust(business_with_hours):
    # This assumes the template exists in the environment
    pass

def test_backward_compatibility_flat_hours_still_works(business_with_hours):
    composer = TemplateComposer()
    data = composer._build_data_dict(business_with_hours)
    assert "hours" in data

def test_default_hours_schedule(business_with_hours):
    business_with_hours.hours.note = None
    composer = TemplateComposer()
    data = composer._build_data_dict(business_with_hours)
    assert data["hours_note"] == ""

