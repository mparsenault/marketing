import transform


def _rec(fields, rec_id="rec1"):
    return {"id": rec_id, "fields": fields}


def test_record_to_project_maps_fields():
    p = transform.record_to_project(_rec({
        "Project_No": "24-01",
        "Entreprise": "Elem",
        "NomDuProjet": "Usine X",
        "Client": "ACME",
        "descFR": "desc fr",
        "DateDebut": "2024-01-05",
        "DateFermeture": "2024-06-10",
        "ResponsableBureau": "Marie",
        "ResponsableDeChantier": "Luc",
        "photoAvailable": True,
        "online": True,
        "postDone": True,
        "confidential": True,
        "confidentialReason": "NDA",
        "notes": "note",
        "descEN": "desc en",
    }))
    assert p["id"] == "rec1"
    assert p["project_no"] == "24-01"
    assert p["company"] == "Elem"
    assert p["project"] == "Usine X"
    assert p["dates"] == "2024-01-05 - 2024-06-10"
    assert p["photo_available"] is True
    assert p["post_done"] is True
    assert p["confidential"] is True
    assert p["confidential_reason"] == "NDA"


def test_record_to_project_missing_checkboxes_default_false():
    # Airtable omet les cases décochées et les textes vides
    p = transform.record_to_project(_rec({"Project_No": "9", "Entreprise": "Ondel"}))
    assert p["photo_available"] is False
    assert p["online"] is False
    assert p["post_done"] is False
    assert p["confidential"] is False
    assert p["confidential_reason"] == ""
    assert p["notes"] == ""
    assert p["dates"] == ""


def test_build_dates_display():
    assert transform.build_dates_display("2024-01-05", "2024-06-10") == "2024-01-05 - 2024-06-10"
    assert transform.build_dates_display("2024-01-05", "") == "2024-01-05"
    assert transform.build_dates_display("", "") == ""


def test_extract_years():
    assert transform.extract_years("2024-01-05 - 2024-06-10") == [2024]
    assert transform.extract_years("2019-01-01 - 2023-12-31") == [2019, 2023]
    assert transform.extract_years("") == []
    assert transform.extract_years("N/A") == []


def test_filter_recent_keeps_min_year_within_span():
    projects = [
        {"dates": "2024-01-01 - 2024-06-01"},  # min 2024 >= 2021 → gardé
        {"dates": "2018-01-01 - 2024-01-01"},  # min 2018 < 2021 → exclu
        {"dates": ""},                          # aucune année → exclu
    ]
    kept = transform.filter_recent(projects, current_year=2026, span=5)
    assert len(kept) == 1
    assert kept[0]["dates"].startswith("2024")


def test_apply_filters_search_and_company():
    projects = [
        {"project": "Usine X", "client": "ACME", "project_no": "1", "company": "Elem",
         "desc_fr": "", "notes": "", "dates": "2024-01-01", "photo_available": False,
         "online": False, "post_done": False},
        {"project": "Pont Y", "client": "BETA", "project_no": "2", "company": "Ondel",
         "desc_fr": "", "notes": "", "dates": "2024-01-01", "photo_available": False,
         "online": False, "post_done": False},
    ]
    f = {"search": "acme", "company": "", "year_from": "", "year_to": "",
         "without_photo": False, "without_online": False, "without_post": False}
    out = transform.apply_filters(projects, f)
    assert len(out) == 1 and out[0]["project"] == "Usine X"

    f2 = {**f, "search": "", "company": "Ondel"}
    out2 = transform.apply_filters(projects, f2)
    assert len(out2) == 1 and out2[0]["company"] == "Ondel"


def test_apply_filters_toggles_show_missing():
    projects = [
        {"project": "A", "client": "", "project_no": "1", "company": "", "desc_fr": "",
         "notes": "", "dates": "2024", "photo_available": True, "online": True, "post_done": True},
        {"project": "B", "client": "", "project_no": "2", "company": "", "desc_fr": "",
         "notes": "", "dates": "2024", "photo_available": False, "online": False, "post_done": False},
    ]
    base = {"search": "", "company": "", "year_from": "", "year_to": "",
            "without_photo": False, "without_online": False, "without_post": False}
    # "Sans photo dispo" ne garde que ceux sans photo
    out = transform.apply_filters(projects, {**base, "without_photo": True})
    assert [p["project"] for p in out] == ["B"]
    out = transform.apply_filters(projects, {**base, "without_post": True})
    assert [p["project"] for p in out] == ["B"]


def test_apply_filters_year_range():
    projects = [
        {"project": "A", "client": "", "project_no": "1", "company": "", "desc_fr": "",
         "notes": "", "dates": "2020-01-01 - 2020-06-01", "photo_available": False,
         "online": False, "post_done": False},
        {"project": "B", "client": "", "project_no": "2", "company": "", "desc_fr": "",
         "notes": "", "dates": "2024-01-01 - 2024-06-01", "photo_available": False,
         "online": False, "post_done": False},
    ]
    base = {"search": "", "company": "", "year_from": "2023", "year_to": "",
            "without_photo": False, "without_online": False, "without_post": False}
    out = transform.apply_filters(projects, base)
    assert [p["project"] for p in out] == ["B"]


def test_sort_by_end_date_desc_empties_last():
    projects = [
        {"project": "A", "date_debut": "2024-01-01", "date_fermeture": "2024-03-01"},
        {"project": "B", "date_debut": "2025-01-01", "date_fermeture": "2025-02-01"},
        {"project": "C", "date_debut": "", "date_fermeture": ""},
    ]
    out = transform.sort_by_end_date_desc(projects)
    assert [p["project"] for p in out] == ["B", "A", "C"]


def test_compute_stats():
    projects = [
        {"photo_available": True, "online": True, "post_done": True},
        {"photo_available": True, "online": False, "post_done": False},
        {"photo_available": False, "online": False, "post_done": False},
    ]
    s = transform.compute_stats(projects)
    assert s == {"total": 3, "photos": 2, "online": 1, "todo": 2}


def test_company_and_year_options():
    projects = [
        {"company": "Ondel", "dates": "2024-01-01 - 2024-06-01"},
        {"company": "Elem", "dates": "2022-01-01"},
        {"company": "Elem", "dates": ""},
    ]
    assert transform.company_options(projects) == ["Elem", "Ondel"]
    assert transform.year_options(projects) == [2022, 2024]


def test_record_to_project_maps_approval_fields():
    rec = {"id": "rec1", "fields": {
        "StatutPublication": "En attente d'approbation",
        "BrouillonPost": "Un super post",
        "BrouillonDescFR": "desc fr", "BrouillonDescEN": "desc en",
        "ResponsableBureauEmail": "resp@elem.global",
        "ApprouvéPar": "chef@elem.global", "DateApprobation": "2026-07-17",
        "RaisonRejet": "trop court",
        "LienPhotosSharePoint": "https://sp/24-01",
    }}
    p = transform.record_to_project(rec)
    assert p["statut_publication"] == "En attente d'approbation"
    assert p["brouillon_post"] == "Un super post"
    assert p["brouillon_desc_fr"] == "desc fr"
    assert p["brouillon_desc_en"] == "desc en"
    assert p["responsable_bureau_email"] == "resp@elem.global"
    assert p["approuve_par"] == "chef@elem.global"
    assert p["date_approbation"] == "2026-07-17"
    assert p["raison_rejet"] == "trop court"
    assert p["lien_photos"] == "https://sp/24-01"


def test_record_to_project_approval_fields_default_empty():
    p = transform.record_to_project({"id": "rec1", "fields": {}})
    assert p["statut_publication"] == ""
    assert p["lien_photos"] == ""
