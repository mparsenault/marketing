"""Notification d'approbation par DM Teams via Microsoft Graph.

Helpers purs (lien, message) testables directement ; l'envoi réseau est isolé
dans des fonctions privées monkeypatchables. Voir le runbook pour l'inscription
d'app Azure AD et les permissions Graph.
"""

import html
import os

import requests

_TIMEOUT = 30
_GRAPH = "https://graph.microsoft.com/v1.0"


def build_approval_link(base_app_url: str, record_id: str) -> str:
    return f"{base_app_url.rstrip('/')}/?record={record_id}"


def build_message(project_no: str, project_name: str,
                  post_excerpt: str, link: str) -> str:
    return (
        f"<p><b>Brouillon à approuver — "
        f"{html.escape(project_no)} · {html.escape(project_name)}</b></p>"
        f"<p>{html.escape(post_excerpt)}</p>"
        f'<p><a href="{html.escape(link, quote=True)}">'
        f"Ouvrir la page d'approbation</a></p>"
    )


def get_graph_config() -> dict:
    """Config Graph : st.secrets puis fallback os.environ."""
    vals = {}
    keys = {
        "tenant": "GRAPH_TENANT_ID", "client_id": "GRAPH_CLIENT_ID",
        "client_secret": "GRAPH_CLIENT_SECRET", "sender_id": "GRAPH_SENDER_ID",
        "base_app_url": "BASE_APP_URL",
    }
    try:
        import streamlit as st
        for k, env in keys.items():
            vals[k] = st.secrets.get(env)
    except Exception:
        pass
    for k, env in keys.items():
        vals[k] = vals.get(k) or os.environ.get(env)
    missing = [env for k, env in keys.items() if not vals.get(k)]
    if missing:
        raise RuntimeError("Config Graph manquante : " + ", ".join(missing))
    return vals


def _graph_token(cfg: dict) -> str:
    r = requests.post(
        f"https://login.microsoftonline.com/{cfg['tenant']}/oauth2/v2.0/token",
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_chat(token: str, sender_id: str, recipient_email: str) -> str:
    body = {
        "chatType": "oneOnOne",
        "members": [
            {"@odata.type": "#microsoft.graph.aadUserConversationMember",
             "roles": ["owner"],
             "user@odata.bind": f"{_GRAPH}/users('{sender_id}')"},
            {"@odata.type": "#microsoft.graph.aadUserConversationMember",
             "roles": ["owner"],
             "user@odata.bind": f"{_GRAPH}/users('{recipient_email}')"},
        ],
    }
    r = requests.post(f"{_GRAPH}/chats", headers=_headers(token),
                      json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["id"]


def _post_message(token: str, chat_id: str, html: str) -> None:
    body = {"body": {"contentType": "html", "content": html}}
    r = requests.post(f"{_GRAPH}/chats/{chat_id}/messages",
                      headers=_headers(token), json=body, timeout=_TIMEOUT)
    r.raise_for_status()


def send_approval_request(recipient_email: str, html: str) -> None:
    """Envoie le DM Teams d'approbation au responsable bureau."""
    cfg = get_graph_config()
    token = _graph_token(cfg)
    chat_id = _create_chat(token, cfg["sender_id"], recipient_email)
    _post_message(token, chat_id, html)
