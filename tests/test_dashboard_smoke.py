import airtable_client
import dashboard
from streamlit.testing.v1 import AppTest


def _fake_records():
    return [
        {"id": "rec1", "fields": {
            "Project_No": "24-01", "Entreprise": "Elem", "NomDuProjet": "Usine X",
            "Client": "ACME", "DateDebut": "2025-01-01", "DateFermeture": "2025-06-01",
            "photoAvailable": True,
        }},
        {"id": "rec2", "fields": {
            "Project_No": "24-07", "Entreprise": "Ondel", "NomDuProjet": "Pont Y",
            "Client": "BETA", "DateDebut": "2025-02-01", "DateFermeture": "2025-03-01",
            "confidential": True, "confidentialReason": "NDA",
        }},
    ]


def test_dashboard_renders_table(monkeypatch):
    monkeypatch.setattr(airtable_client, "get_config",
                        lambda: {"pat": "x", "base_id": "app", "table_name": "Projets"})
    monkeypatch.setattr(airtable_client, "fetch_projects", lambda **k: _fake_records())
    dashboard.load_projects.clear()

    at = AppTest.from_string("import dashboard; dashboard.render()")
    at.run()

    assert not at.exception
    # 4 cartes de stats
    assert len(at.metric) == 4
    assert any(m.label == "📁 Total projets" for m in at.metric)
    # Le tableau est rendu
    assert len(at.dataframe) == 1
