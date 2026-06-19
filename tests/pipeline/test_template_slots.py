from pipeline.template_slots import find_unresolved_slots


def test_find_unresolved_slots_empty_when_all_resolved():
    assert find_unresolved_slots("<html><h1>Bright Smile Dental</h1></html>") == []


def test_find_unresolved_slots_returns_unique_slots_in_order():
    html = "<p>{{ business_name }}</p><p>{{hero_description}}</p><p>{{ business_name }}</p><p>{{cta_primary}}</p>"
    assert find_unresolved_slots(html) == ["{{ business_name }}", "{{hero_description}}", "{{cta_primary}}"]
