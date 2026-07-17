"""Couche HTTP Airtable (lecture/écriture). Aucune logique métier ici."""

import os
import time
import urllib.parse

import requests

EDITABLE_FIELDS = [
    "photoAvailable", "online", "postDone",
    "confidential", "confidentialReason", "notes", "descEN",
    # Cycle de vie brouillon → approbation (sous-projet A)
    "StatutPublication", "BrouillonPost", "BrouillonDescFR", "BrouillonDescEN",
    "ResponsableBureauEmail", "ApprouvéPar", "DateApprobation", "RaisonRejet",
]

_RATE_SLEEP = 0.22  # ~4.5 req/s, sous la limite Airtable de 5/s
_TIMEOUT = 30


def get_config() -> dict:
    """Lit la config Airtable depuis st.secrets, avec fallback os.environ."""
    pat = base_id = table_name = None
    try:
        import streamlit as st
        pat = st.secrets.get("AIRTABLE_PAT")
        base_id = st.secrets.get("AIRTABLE_BASE_ID")
        table_name = st.secrets.get("AIRTABLE_TABLE_NAME")
    except Exception:
        pass
    pat = pat or os.environ.get("AIRTABLE_PAT")
    base_id = base_id or os.environ.get("AIRTABLE_BASE_ID")
    table_name = table_name or os.environ.get("AIRTABLE_TABLE_NAME", "Projets")
    if not (pat and base_id):
        raise RuntimeError(
            "Config Airtable manquante : AIRTABLE_PAT et AIRTABLE_BASE_ID requis "
            "dans .streamlit/secrets.toml."
        )
    return {"pat": pat, "base_id": base_id, "table_name": table_name}


def _table_url(base_id: str, table_name: str) -> str:
    return f"https://api.airtable.com/v0/{base_id}/{urllib.parse.quote(table_name)}"


def _headers(pat: str) -> dict:
    return {"Authorization": f"Bearer {pat}", "Content-Type": "application/json"}


def fetch_projects(pat: str, base_id: str, table_name: str) -> list:
    url = _table_url(base_id, table_name)
    headers = _headers(pat)
    records = []
    offset = None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(_RATE_SLEEP)
    return records


def fetch_project(pat: str, base_id: str, table_name: str, record_id: str) -> dict:
    """Lit un seul enregistrement par id (page d'approbation)."""
    url = f"{_table_url(base_id, table_name)}/{record_id}"
    r = requests.get(url, headers=_headers(pat), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def update_project(pat: str, base_id: str, table_name: str,
                   record_id: str, fields: dict) -> None:
    safe_fields = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
    body = {
        "records": [{"id": record_id, "fields": safe_fields}],
        "typecast": True,
    }
    r = requests.patch(
        _table_url(base_id, table_name),
        headers=_headers(pat),
        json=body,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
