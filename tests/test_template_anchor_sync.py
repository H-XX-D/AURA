from aura_compression.templates import TemplateLibrary

def test_dynamic_template_anchor_refresh():
    template_library = TemplateLibrary()
    dynamic_id = 150

    template_library.sync_dynamic_templates({dynamic_id: "Order number {0} ready"})
    first_record = template_library._records[dynamic_id]
    assert first_record.anchor_casefold == "order number ".casefold()

    template_library.sync_dynamic_templates({dynamic_id: "Dispatch {0} tomorrow"})
    updated_record = template_library._records[dynamic_id]
    assert updated_record.anchor_casefold == "dispatch ".casefold()

    matches = template_library.find_substring_matches("Please confirm dispatch ABC tomorrow.")
    assert any(match.template_id == dynamic_id for match in matches)
