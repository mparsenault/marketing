import airtable_client


class _FakeResp:
    def __init__(self, payload, ok=True, status=200, text=""):
        self._payload = payload
        self.ok = ok
        self.status_code = status
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_projects_paginates(monkeypatch):
    pages = [
        {"records": [{"id": "rec1", "fields": {"Project_No": "1"}}], "offset": "off2"},
        {"records": [{"id": "rec2", "fields": {"Project_No": "2"}}]},
    ]
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        i = calls["n"]
        calls["n"] += 1
        return _FakeResp(pages[i])

    monkeypatch.setattr(airtable_client.requests, "get", fake_get)
    monkeypatch.setattr(airtable_client.time, "sleep", lambda *_: None)

    records = airtable_client.fetch_projects("patX", "appScszc5IPkA58HX", "Projets")
    assert [r["id"] for r in records] == ["rec1", "rec2"]
    assert calls["n"] == 2


def test_update_project_filters_to_editable_fields(monkeypatch):
    captured = {}

    def fake_patch(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp({"records": [{"id": "rec1"}]})

    monkeypatch.setattr(airtable_client.requests, "patch", fake_patch)

    airtable_client.update_project(
        "patX", "appScszc5IPkA58HX", "Projets", "rec1",
        {"online": True, "notes": "x", "Project_No": "HACK", "unknown": 1},
    )
    sent_fields = captured["json"]["records"][0]["fields"]
    assert sent_fields == {"online": True, "notes": "x"}
    assert captured["json"]["records"][0]["id"] == "rec1"
    assert captured["json"]["typecast"] is True


def test_update_project_raises_on_error(monkeypatch):
    def fake_patch(url, headers=None, json=None, timeout=None):
        return _FakeResp({}, ok=False, status=422, text="bad")

    monkeypatch.setattr(airtable_client.requests, "patch", fake_patch)
    import pytest
    with pytest.raises(RuntimeError):
        airtable_client.update_project("patX", "app", "Projets", "rec1", {"online": True})


def test_editable_fields_includes_approval_fields():
    for field in ["StatutPublication", "BrouillonPost", "BrouillonDescFR",
                  "BrouillonDescEN", "ResponsableBureauEmail", "ApprouvéPar",
                  "DateApprobation", "RaisonRejet"]:
        assert field in airtable_client.EDITABLE_FIELDS


def test_update_project_allows_status_field(monkeypatch):
    captured = {}

    def fake_patch(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResp({"records": [{"id": "rec1"}]})

    monkeypatch.setattr(airtable_client.requests, "patch", fake_patch)
    airtable_client.update_project(
        "patX", "app", "Projets", "rec1",
        {"StatutPublication": "Approuvé", "ApprouvéPar": "a@elem.global"},
    )
    sent = captured["json"]["records"][0]["fields"]
    assert sent == {"StatutPublication": "Approuvé", "ApprouvéPar": "a@elem.global"}


def test_fetch_project_gets_single_record(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return _FakeResp({"id": "rec1", "fields": {"Project_No": "24-01"}})

    monkeypatch.setattr(airtable_client.requests, "get", fake_get)
    rec = airtable_client.fetch_project("patX", "appABC", "Projets", "rec1")
    assert rec["id"] == "rec1"
    assert captured["url"].endswith("/Projets/rec1")
