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


# --- build_edit_payload -----------------------------------------------------

def test_build_edit_payload_has_exactly_editable_fields():
    payload = dashboard.build_edit_payload(
        True, False, True, False, "", "some notes", "some desc"
    )
    assert set(payload.keys()) == set(airtable_client.EDITABLE_FIELDS)
    assert set(payload.keys()) == {
        "photoAvailable", "online", "postDone",
        "confidential", "confidentialReason", "notes", "descEN",
    }


def test_build_edit_payload_keeps_reason_when_confidential():
    payload = dashboard.build_edit_payload(
        True, True, False, True, "NDA client", "notes", "desc"
    )
    assert payload["confidential"] is True
    assert payload["confidentialReason"] == "NDA client"


def test_build_edit_payload_clears_reason_when_not_confidential():
    payload = dashboard.build_edit_payload(
        True, True, False, False, "leftover reason text", "notes", "desc"
    )
    assert payload["confidential"] is False
    assert payload["confidentialReason"] == ""
