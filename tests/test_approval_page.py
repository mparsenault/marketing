import airtable_client
import approval_page
from streamlit.testing.v1 import AppTest


def _pending_record():
    return {"id": "rec1", "fields": {
        "Project_No": "24-01", "NomDuProjet": "Usine X", "Client": "ACME",
        "StatutPublication": "En attente d'approbation",
        "BrouillonPost": "Un super post", "BrouillonDescFR": "desc fr",
        "BrouillonDescEN": "desc en", "ResponsableBureau": "Jean Tremblay",
        "sharepointUrl": "https://sp/24-01",
    }}


def test_approval_page_renders_pending_draft(monkeypatch):
    monkeypatch.setattr(airtable_client, "get_config",
                        lambda: {"pat": "x", "base_id": "app", "table_name": "Projets"})
    monkeypatch.setattr(airtable_client, "fetch_project",
                        lambda pat, base_id, table_name, record_id: _pending_record())

    at = AppTest.from_string("import approval_page; approval_page.render('rec1')")
    at.run()

    assert not at.exception
    assert any("Usine X" in md.value for md in at.markdown) \
        or any("Usine X" in sh.value for sh in at.subheader)
    assert any(b.label == "✅ Approuver" for b in at.button)
    assert any(b.label == "❌ Rejeter" for b in at.button)


def test_approval_page_already_processed_hides_buttons(monkeypatch):
    rec = _pending_record()
    rec["fields"]["StatutPublication"] = "Approuvé"
    monkeypatch.setattr(airtable_client, "get_config",
                        lambda: {"pat": "x", "base_id": "app", "table_name": "Projets"})
    monkeypatch.setattr(airtable_client, "fetch_project",
                        lambda pat, base_id, table_name, record_id: rec)

    at = AppTest.from_string("import approval_page; approval_page.render('rec1')")
    at.run()

    assert not at.exception
    assert not any(b.label == "✅ Approuver" for b in at.button)
