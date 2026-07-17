import notifications


def test_build_approval_link_strips_trailing_slash():
    assert notifications.build_approval_link(
        "https://app.elem.global/", "rec1") == "https://app.elem.global/?record=rec1"


def test_build_approval_link_no_slash():
    assert notifications.build_approval_link(
        "https://app.elem.global", "rec1") == "https://app.elem.global/?record=rec1"


def test_build_message_contains_all_parts():
    html = notifications.build_message("24-01", "Usine X", "Extrait du post…",
                                       "https://app/?record=rec1")
    assert "24-01" in html
    assert "Usine X" in html
    assert "Extrait du post…" in html
    assert "https://app/?record=rec1" in html


def test_send_approval_request_orchestrates(monkeypatch):
    calls = []
    monkeypatch.setattr(notifications, "get_graph_config", lambda: {
        "tenant": "t", "client_id": "c", "client_secret": "s",
        "sender_id": "sender-guid", "base_app_url": "https://app"})
    monkeypatch.setattr(notifications, "_graph_token", lambda cfg: "tok")
    monkeypatch.setattr(notifications, "_create_chat",
                        lambda token, sender_id, email: calls.append(("chat", email)) or "chat1")
    monkeypatch.setattr(notifications, "_post_message",
                        lambda token, chat_id, html: calls.append(("msg", chat_id, html)))

    notifications.send_approval_request("resp@elem.global", "<p>hello</p>")

    assert ("chat", "resp@elem.global") in calls
    assert ("msg", "chat1", "<p>hello</p>") in calls


def test_graph_token_parses_access_token(monkeypatch):
    class _R:
        def raise_for_status(self): pass
        def json(self): return {"access_token": "abc123"}

    monkeypatch.setattr(notifications.requests, "post",
                        lambda url, data=None, timeout=None: _R())
    token = notifications._graph_token({
        "tenant": "t", "client_id": "c", "client_secret": "s"})
    assert token == "abc123"
