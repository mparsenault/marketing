import migrate_responsable_email as mig


def test_normalize_lowers_and_trims_spaces():
    assert mig.normalize("  Jean  Tremblay ") == "jean tremblay"


def test_map_name_to_email_found_case_insensitive():
    mapping = {"Jean Tremblay": "jean@elem.global"}
    assert mig.map_name_to_email("jean tremblay", mapping) == "jean@elem.global"


def test_map_name_to_email_unknown_returns_none():
    assert mig.map_name_to_email("Inconnu", {"Jean": "j@elem.global"}) is None


def test_build_migration_updates_maps_and_reports():
    projects = [
        {"id": "rec1", "responsable_bureau": "Jean Tremblay"},
        {"id": "rec2", "responsable_bureau": "Marie Roy"},
        {"id": "rec3", "responsable_bureau": ""},
    ]
    mapping = {"Jean Tremblay": "jean@elem.global"}
    updates, unmapped = mig.build_migration_updates(projects, mapping)
    assert updates == [("rec1", {"ResponsableBureauEmail": "jean@elem.global"})]
    assert unmapped == ["Marie Roy"]
