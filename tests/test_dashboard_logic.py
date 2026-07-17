"""Unit tests for the pure helpers extracted from dashboard.py's render/edit flow."""

import airtable_client
import dashboard


# --- select_project -------------------------------------------------------

def test_select_project_empty_selection_returns_none():
    filtered = [{"id": "rec1"}, {"id": "rec2"}]
    assert dashboard.select_project(filtered, []) is None


def test_select_project_out_of_range_index_returns_none():
    filtered = [{"id": "rec1"}, {"id": "rec2"}]
    assert dashboard.select_project(filtered, [5]) is None


def test_select_project_negative_index_returns_none():
    filtered = [{"id": "rec1"}, {"id": "rec2"}]
    assert dashboard.select_project(filtered, [-1]) is None


def test_select_project_valid_index_returns_project():
    filtered = [{"id": "rec1"}, {"id": "rec2"}]
    assert dashboard.select_project(filtered, [1]) == {"id": "rec2"}


# --- compute_inline_updates -------------------------------------------------

def _projects():
    return [{"id": "rec1"}, {"id": "rec2"}, {"id": "rec3"}]


def test_compute_inline_updates_empty_delta_returns_empty():
    assert dashboard.compute_inline_updates({}, _projects()) == []


def test_compute_inline_updates_single_checkbox_one_field():
    updates = dashboard.compute_inline_updates({0: {"🌐": True}}, _projects())
    assert updates == [("rec1", {"online": True})]


def test_compute_inline_updates_maps_all_labels():
    edited = {1: {"📷": True, "📱": False}}
    updates = dashboard.compute_inline_updates(edited, _projects())
    assert updates == [("rec2", {"photoAvailable": True, "postDone": False})]


def test_compute_inline_updates_confidential_false_clears_reason():
    updates = dashboard.compute_inline_updates({0: {"🔒": False}}, _projects())
    assert updates == [("rec1", {"confidential": False, "confidentialReason": ""})]


def test_compute_inline_updates_confidential_true_keeps_reason_untouched():
    updates = dashboard.compute_inline_updates({0: {"🔒": True}}, _projects())
    assert updates == [("rec1", {"confidential": True})]


def test_compute_inline_updates_out_of_range_index_ignored():
    assert dashboard.compute_inline_updates({9: {"🌐": True}}, _projects()) == []


def test_compute_inline_updates_unknown_column_ignored():
    assert dashboard.compute_inline_updates({0: {"Projet": "x"}}, _projects()) == []


def test_compute_inline_updates_multiple_rows():
    edited = {0: {"🌐": True}, 2: {"📱": True}}
    updates = dashboard.compute_inline_updates(edited, _projects())
    assert ("rec1", {"online": True}) in updates
    assert ("rec3", {"postDone": True}) in updates
    assert len(updates) == 2


# --- build_text_payload -----------------------------------------------------

def test_build_text_payload_has_exactly_text_fields():
    payload = dashboard.build_text_payload("mes notes", "my desc", "NDA")
    assert payload == {"notes": "mes notes", "descEN": "my desc",
                       "confidentialReason": "NDA"}


# --- send_for_approval -------------------------------------------------------

def test_send_for_approval_sets_status_then_notifies(monkeypatch):
    import dashboard
    import notifications
    calls = {}
    monkeypatch.setattr(airtable_client, "get_config",
                        lambda: {"pat": "x", "base_id": "app", "table_name": "Projets"})
    monkeypatch.setattr(airtable_client, "update_project",
                        lambda pat, base_id, table_name, rec_id, payload:
                        calls.setdefault("update", (rec_id, payload)))
    monkeypatch.setattr(notifications, "get_graph_config",
                        lambda: {"base_app_url": "https://app"})
    monkeypatch.setattr(notifications, "send_approval_request",
                        lambda email, html: calls.setdefault("notify", (email, html)))

    project = {"id": "rec1", "project_no": "24-01", "project": "Usine X",
               "brouillon_post": "Un post", "responsable_bureau_email": "r@elem.global"}
    dashboard.send_for_approval(project)

    assert calls["update"] == ("rec1", {"StatutPublication": "En attente d'approbation"})
    assert calls["notify"][0] == "r@elem.global"
    assert "https://app/?record=rec1" in calls["notify"][1]
