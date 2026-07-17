# Fondation Airtable + approbation via lien Teams — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter à l'app Streamlit le cycle de vie « brouillon → approbation » : un statut Airtable, une action « Envoyer pour approbation » (dashboard) qui notifie le responsable bureau par DM Teams, et une page d'approbation à enregistrement unique atteinte par un lien.

**Architecture:** L'app reste mono-fichier `app.py` qui, après la garde SSO, route selon `st.query_params` : `?record=recX` → `approval_page.render()`, sinon `dashboard.render()`. La logique décisionnelle (payloads de statut, résolution d'id, mapping nom→email, construction du lien/message) vit dans des **fonctions pures testées** (`approvals.py`, `notifications.py`, `migrate_responsable_email.py`) ; le rendu Streamlit et les appels réseau (Airtable, Microsoft Graph) restent des couches fines.

**Tech Stack:** Python 3.9, Streamlit (`streamlit[auth]`), `requests`, Airtable REST API, Microsoft Graph REST API, pytest.

## Global Constraints

- **Python 3.9** — pas de syntaxe 3.10+ (pas de `match`, pas de `X | Y` en annotation).
- **Layout plat** — modules à la racine du dépôt, tests dans `tests/` important les modules directement (`import approvals`). Pas de dossier `src/`.
- **Aucune nouvelle dépendance** — Microsoft Graph est appelé via `requests` (jeton client-credentials + POST). Ne pas ajouter `msal`.
- **`airtable_client.update_project` filtre les champs à `EDITABLE_FIELDS`** — tout nouveau champ écrit DOIT être ajouté à cette liste, sinon le PATCH le supprime silencieusement.
- **Champs Airtable (noms exacts, avec accents)** : `StatutPublication`, `BrouillonPost`, `BrouillonDescFR`, `BrouillonDescEN`, `ResponsableBureauEmail`, `ApprouvéPar`, `DateApprobation`, `RaisonRejet`, `LienPhotosSharePoint` (formule, lecture seule).
- **Valeurs de `StatutPublication`** : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`. (Pas de `Rejeté` : le rejet renvoie à `À rédiger`.)
- **Copie UI en français.**
- **Tests** : pytest + `monkeypatch`, motif `_FakeResp` pour le HTTP (voir `tests/test_airtable_client.py`). Commits fréquents (un par tâche minimum).
- **Rate limit Airtable** : ~4.5 req/s (constante `_RATE_SLEEP` existante).

---

### Task 1: Étendre `airtable_client` — champs éditables + lecture d'un enregistrement

**Files:**
- Modify: `airtable_client.py:9-12` (constante `EDITABLE_FIELDS`), ajout d'une fonction `fetch_project`
- Test: `tests/test_airtable_client.py`

**Interfaces:**
- Consumes: rien (première tâche).
- Produces:
  - `EDITABLE_FIELDS` étendue avec les 8 nouveaux champs écrivables.
  - `fetch_project(pat: str, base_id: str, table_name: str, record_id: str) -> dict` → renvoie un enregistrement Airtable `{"id": ..., "fields": {...}}`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_airtable_client.py` :

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_airtable_client.py -q`
Expected: FAIL (`StatutPublication` absent de `EDITABLE_FIELDS` ; `fetch_project` non défini).

- [ ] **Step 3: Étendre `EDITABLE_FIELDS`**

Dans `airtable_client.py`, remplacer la constante :

```python
EDITABLE_FIELDS = [
    "photoAvailable", "online", "postDone",
    "confidential", "confidentialReason", "notes", "descEN",
    # Cycle de vie brouillon → approbation (sous-projet A)
    "StatutPublication", "BrouillonPost", "BrouillonDescFR", "BrouillonDescEN",
    "ResponsableBureauEmail", "ApprouvéPar", "DateApprobation", "RaisonRejet",
]
```

- [ ] **Step 4: Ajouter `fetch_project`**

Dans `airtable_client.py`, après `fetch_projects` :

```python
def fetch_project(pat: str, base_id: str, table_name: str, record_id: str) -> dict:
    """Lit un seul enregistrement par id (page d'approbation)."""
    url = f"{_table_url(base_id, table_name)}/{record_id}"
    r = requests.get(url, headers=_headers(pat), timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_airtable_client.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add airtable_client.py tests/test_airtable_client.py
git commit -m "feat: champs d'approbation éditables + fetch_project (fondation A)"
```

---

### Task 2: Étendre `transform.record_to_project` — exposer les nouveaux champs

**Files:**
- Modify: `transform.py:22-45` (fonction `record_to_project`)
- Test: `tests/test_transform.py`

**Interfaces:**
- Consumes: rien.
- Produces: le dict projet gagne les clés `statut_publication`, `brouillon_post`, `brouillon_desc_fr`, `brouillon_desc_en`, `responsable_bureau_email`, `approuve_par`, `date_approbation`, `raison_rejet`, `lien_photos` (toutes `str`, défaut `""`).

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `tests/test_transform.py` :

```python
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
```

Le fichier `tests/test_transform.py` importe déjà `transform` ; s'il ne le fait pas, ajouter `import transform` en tête.

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_transform.py -q`
Expected: FAIL (`KeyError: 'statut_publication'`).

- [ ] **Step 3: Étendre `record_to_project`**

Dans `transform.py`, dans le `return {...}` de `record_to_project`, ajouter avant l'accolade fermante (après la clé `"desc_en"`) :

```python
        "desc_en": f.get("descEN", "") or "",
        "statut_publication": f.get("StatutPublication", "") or "",
        "brouillon_post": f.get("BrouillonPost", "") or "",
        "brouillon_desc_fr": f.get("BrouillonDescFR", "") or "",
        "brouillon_desc_en": f.get("BrouillonDescEN", "") or "",
        "responsable_bureau_email": f.get("ResponsableBureauEmail", "") or "",
        "approuve_par": f.get("ApprouvéPar", "") or "",
        "date_approbation": f.get("DateApprobation", "") or "",
        "raison_rejet": f.get("RaisonRejet", "") or "",
        "lien_photos": f.get("LienPhotosSharePoint", "") or "",
```

(La ligne `"desc_en": ...` existe déjà ; conserver une seule occurrence, ajouter les suivantes.)

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `.venv/bin/python -m pytest tests/test_transform.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add transform.py tests/test_transform.py
git commit -m "feat: transform expose les champs d'approbation"
```

---

### Task 3: `approvals.py` — fonctions pures de routage et de payloads

**Files:**
- Create: `approvals.py`
- Test: `tests/test_approvals.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `target_record_id(query_params) -> str | None` — renvoie l'id (trimé) du paramètre `record`, ou `None` si absent/vide. `query_params` expose `.get`.
  - `build_pending_payload() -> dict` → `{"StatutPublication": "En attente d'approbation"}`.
  - `build_approval_payload(approver_email: str, today: str) -> dict` → `{"StatutPublication": "Approuvé", "ApprouvéPar": approver_email, "DateApprobation": today}`.
  - `build_rejection_payload(reason: str) -> dict` → `{"StatutPublication": "À rédiger", "RaisonRejet": reason}`.
  - `PENDING = "En attente d'approbation"` (constante réutilisée par la page d'approbation).

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_approvals.py` :

```python
import approvals


def test_target_record_id_present():
    assert approvals.target_record_id({"record": "recABC"}) == "recABC"


def test_target_record_id_absent_returns_none():
    assert approvals.target_record_id({}) is None


def test_target_record_id_blank_returns_none():
    assert approvals.target_record_id({"record": "   "}) is None


def test_target_record_id_is_trimmed():
    assert approvals.target_record_id({"record": "  recX "}) == "recX"


def test_build_pending_payload():
    assert approvals.build_pending_payload() == {
        "StatutPublication": "En attente d'approbation"}


def test_build_approval_payload():
    assert approvals.build_approval_payload("a@elem.global", "2026-07-17") == {
        "StatutPublication": "Approuvé",
        "ApprouvéPar": "a@elem.global",
        "DateApprobation": "2026-07-17",
    }


def test_build_rejection_payload_sets_a_rediger():
    assert approvals.build_rejection_payload("trop court") == {
        "StatutPublication": "À rédiger",
        "RaisonRejet": "trop court",
    }
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_approvals.py -q`
Expected: FAIL (`ModuleNotFoundError: approvals`).

- [ ] **Step 3: Écrire `approvals.py`**

```python
"""Fonctions pures du cycle d'approbation : routage et payloads de statut.

Aucun I/O ici (ni Streamlit, ni réseau) — testables directement.
"""

PENDING = "En attente d'approbation"


def target_record_id(query_params):
    """Id de l'enregistrement à approuver, depuis ?record=... ; None si absent."""
    raw = query_params.get("record")
    if not raw:
        return None
    value = raw.strip()
    return value or None


def build_pending_payload() -> dict:
    """Passe un projet en attente d'approbation."""
    return {"StatutPublication": PENDING}


def build_approval_payload(approver_email: str, today: str) -> dict:
    """Approbation : statut + audit (qui, quand)."""
    return {
        "StatutPublication": "Approuvé",
        "ApprouvéPar": approver_email,
        "DateApprobation": today,
    }


def build_rejection_payload(reason: str) -> dict:
    """Rejet : renvoie à « À rédiger » en conservant le motif comme feedback."""
    return {"StatutPublication": "À rédiger", "RaisonRejet": reason}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_approvals.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add approvals.py tests/test_approvals.py
git commit -m "feat: approvals — routage et payloads de statut (fonctions pures)"
```

---

### Task 4: `notifications.py` — lien, message et envoi DM Teams (Graph)

**Files:**
- Create: `notifications.py`
- Test: `tests/test_notifications.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `build_approval_link(base_app_url: str, record_id: str) -> str` → `"<base sans / final>/?record=<id>"`.
  - `build_message(project_no: str, project_name: str, post_excerpt: str, link: str) -> str` → contenu HTML contenant les 4 éléments.
  - `get_graph_config() -> dict` → `{"tenant", "client_id", "client_secret", "sender_id", "base_app_url"}` (secrets → env).
  - `send_approval_request(recipient_email: str, html: str) -> None` — envoie le DM Teams via Graph (jeton client-credentials → création du chat 1:1 → post du message).

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_notifications.py` :

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_notifications.py -q`
Expected: FAIL (`ModuleNotFoundError: notifications`).

- [ ] **Step 3: Écrire `notifications.py`**

```python
"""Notification d'approbation par DM Teams via Microsoft Graph.

Helpers purs (lien, message) testables directement ; l'envoi réseau est isolé
dans des fonctions privées monkeypatchables. Voir le runbook pour l'inscription
d'app Azure AD et les permissions Graph.
"""

import os

import requests

_TIMEOUT = 30
_GRAPH = "https://graph.microsoft.com/v1.0"


def build_approval_link(base_app_url: str, record_id: str) -> str:
    return f"{base_app_url.rstrip('/')}/?record={record_id}"


def build_message(project_no: str, project_name: str,
                  post_excerpt: str, link: str) -> str:
    return (
        f"<p><b>Brouillon à approuver — {project_no} · {project_name}</b></p>"
        f"<p>{post_excerpt}</p>"
        f'<p><a href="{link}">Ouvrir la page d\'approbation</a></p>'
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
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_notifications.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add notifications.py tests/test_notifications.py
git commit -m "feat: notifications — lien, message et envoi DM Teams (Graph)"
```

---

### Task 5: `migrate_responsable_email.py` — mapping nom → email

**Files:**
- Create: `migrate_responsable_email.py`
- Test: `tests/test_migrate_responsable_email.py`

**Interfaces:**
- Consumes: `transform.record_to_project` (Task 2), `airtable_client` (Task 1).
- Produces:
  - `normalize(name: str) -> str` — minuscule, espaces internes réduits, trimé.
  - `map_name_to_email(name: str, mapping: dict) -> str | None` — email si le nom (normalisé) est dans `mapping`, sinon `None`.
  - `build_migration_updates(projects: list, mapping: dict) -> tuple` → `(updates, unmapped)` où `updates = [(record_id, {"ResponsableBureauEmail": email}), ...]` et `unmapped = [noms triés uniques non résolus]`. Ignore les projets sans `responsable_bureau`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_migrate_responsable_email.py` :

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_migrate_responsable_email.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Écrire `migrate_responsable_email.py`**

```python
"""Migration : peupler ResponsableBureauEmail depuis le texte ResponsableBureau.

Usage : python migrate_responsable_email.py   (lit MAPPING ci-dessous)
La fonction pure build_migration_updates est testée ; le runner main() applique.
"""

import airtable_client
import transform

# Correspondance nom (tel qu'écrit dans Airtable) → email @elem.global.
# À compléter au runbook avant exécution.
MAPPING = {
    # "Jean Tremblay": "jean.tremblay@elem.global",
}


def normalize(name: str) -> str:
    return " ".join((name or "").split()).lower()


def map_name_to_email(name: str, mapping: dict):
    lookup = {normalize(k): v for k, v in mapping.items()}
    return lookup.get(normalize(name))


def build_migration_updates(projects: list, mapping: dict):
    updates = []
    unmapped = set()
    for p in projects:
        name = p.get("responsable_bureau", "")
        if not name:
            continue
        email = map_name_to_email(name, mapping)
        if email:
            updates.append((p["id"], {"ResponsableBureauEmail": email}))
        else:
            unmapped.add(name)
    return updates, sorted(unmapped)


def main():
    cfg = airtable_client.get_config()
    records = airtable_client.fetch_projects(**cfg)
    projects = [transform.record_to_project(r) for r in records]
    updates, unmapped = build_migration_updates(projects, MAPPING)
    for rec_id, payload in updates:
        airtable_client.update_project(
            cfg["pat"], cfg["base_id"], cfg["table_name"], rec_id, payload)
    print(f"{len(updates)} projet(s) mis à jour.")
    if unmapped:
        print("Noms non mappés (à compléter dans MAPPING) :")
        for name in unmapped:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_migrate_responsable_email.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrate_responsable_email.py tests/test_migrate_responsable_email.py
git commit -m "feat: script de migration ResponsableBureau -> Email"
```

---

### Task 6: Page d'approbation + routage `app.py`

**Files:**
- Create: `approval_page.py`
- Modify: `app.py:29-30` (routage après la garde SSO)
- Test: `tests/test_approval_page.py`

**Interfaces:**
- Consumes: `approvals` (Task 3), `airtable_client.fetch_project`/`update_project` (Task 1), `transform.record_to_project` (Task 2).
- Produces: `approval_page.render(record_id: str) -> None`.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_approval_page.py` :

```python
import airtable_client
import approval_page
from streamlit.testing.v1 import AppTest


def _pending_record():
    return {"id": "rec1", "fields": {
        "Project_No": "24-01", "NomDuProjet": "Usine X", "Client": "ACME",
        "StatutPublication": "En attente d'approbation",
        "BrouillonPost": "Un super post", "BrouillonDescFR": "desc fr",
        "BrouillonDescEN": "desc en", "ResponsableBureau": "Jean Tremblay",
        "LienPhotosSharePoint": "https://sp/24-01",
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
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_approval_page.py -q`
Expected: FAIL (`ModuleNotFoundError: approval_page`).

- [ ] **Step 3: Écrire `approval_page.py`**

```python
"""Page Streamlit d'approbation d'un seul brouillon (atteinte via ?record=)."""

from datetime import date

import streamlit as st

import airtable_client
import approvals
import transform


def _load(record_id: str):
    cfg = airtable_client.get_config()
    record = airtable_client.fetch_project(
        cfg["pat"], cfg["base_id"], cfg["table_name"], record_id)
    return cfg, transform.record_to_project(record)


def _save(cfg: dict, record_id: str, payload: dict) -> None:
    airtable_client.update_project(
        cfg["pat"], cfg["base_id"], cfg["table_name"], record_id, payload)
    st.cache_data.clear()


def render(record_id: str) -> None:
    st.title("✅ Approbation d'un brouillon")
    try:
        cfg, p = _load(record_id)
    except Exception as e:  # noqa: BLE001
        st.error(f"Brouillon introuvable ({record_id}) : {e}")
        return

    st.subheader(f"{p['project_no']} — {p['project'] or 'Projet'}")
    st.caption(f"Client : {p['client'] or '—'} · "
               f"Resp. bureau : {p['responsable_bureau'] or '—'}")
    if p["lien_photos"]:
        st.markdown(f"[📷 Voir les photos]({p['lien_photos']})")

    st.markdown("**Post réseaux**")
    st.info(p["brouillon_post"] or "—")
    st.markdown("**Description FR**")
    st.info(p["brouillon_desc_fr"] or "—")
    st.markdown("**Description EN**")
    st.info(p["brouillon_desc_en"] or "—")

    if p["statut_publication"] != approvals.PENDING:
        st.warning(f"Ce brouillon n'est pas en attente d'approbation "
                   f"(statut : {p['statut_publication'] or '—'}).")
        return

    st.divider()
    col_ok, col_no = st.columns(2)
    if col_ok.button("✅ Approuver", type="primary"):
        email = (getattr(st.user, "email", "") or "")
        _save(cfg, record_id,
              approvals.build_approval_payload(email, date.today().isoformat()))
        st.success("Brouillon approuvé ✅")
        st.stop()

    with col_no:
        reason = st.text_input("Motif du rejet")
        if st.button("❌ Rejeter"):
            if not reason.strip():
                st.error("Indiquez un motif de rejet.")
            else:
                _save(cfg, record_id, approvals.build_rejection_payload(reason))
                st.success("Brouillon rejeté — renvoyé à « À rédiger ».")
                st.stop()
```

- [ ] **Step 4: Router dans `app.py`**

Dans `app.py`, remplacer les lignes 29-30 (`import dashboard` / `dashboard.render()`) par :

```python
    import approvals
    record_id = approvals.target_record_id(st.query_params)
    if record_id:
        import approval_page
        approval_page.render(record_id)
    else:
        import dashboard
        dashboard.render()
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_approval_page.py tests/test_app_gate.py -q`
Expected: PASS (la garde de connexion reste intacte : sans `record`, on tombe sur le dashboard ; l'écran de login s'affiche toujours quand non connecté).

- [ ] **Step 6: Commit**

```bash
git add approval_page.py app.py tests/test_approval_page.py
git commit -m "feat: page d'approbation à enregistrement unique + routage ?record="
```

---

### Task 7: Action « Envoyer pour approbation » dans le dashboard

**Files:**
- Modify: `dashboard.py` (fonction `_render_text_panel`, après le formulaire d'édition)
- Test: `tests/test_dashboard_logic.py`, `tests/test_dashboard_smoke.py`

**Interfaces:**
- Consumes: `approvals.build_pending_payload` (Task 3), `notifications.build_approval_link`/`build_message`/`send_approval_request`/`get_graph_config` (Task 4), `airtable_client.update_project` (Task 1).
- Produces: `dashboard.send_for_approval(project: dict) -> None` (helper testable qui écrit le statut puis notifie) et un bouton « 📤 Envoyer pour approbation » dans le panneau texte.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `tests/test_dashboard_logic.py` :

```python
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
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_dashboard_logic.py::test_send_for_approval_sets_status_then_notifies -q`
Expected: FAIL (`AttributeError: module 'dashboard' has no attribute 'send_for_approval'`).

- [ ] **Step 3: Écrire `send_for_approval` et le bouton**

Dans `dashboard.py`, ajouter les imports en tête (après `import transform`) :

```python
import approvals
import notifications
```

Ajouter la fonction (près de `build_text_payload`) :

```python
def send_for_approval(project: dict) -> None:
    """Passe le projet en attente d'approbation et notifie le responsable."""
    cfg = airtable_client.get_config()
    airtable_client.update_project(
        cfg["pat"], cfg["base_id"], cfg["table_name"],
        project["id"], approvals.build_pending_payload())
    st.cache_data.clear()
    graph = notifications.get_graph_config()
    link = notifications.build_approval_link(graph["base_app_url"], project["id"])
    html = notifications.build_message(
        project["project_no"], project["project"] or project["project_no"],
        (project["brouillon_post"] or "")[:200], link)
    notifications.send_approval_request(project["responsable_bureau_email"], html)
```

Dans `_render_text_panel`, après le bloc `if submitted:` (fin de la fonction), ajouter :

```python
    st.divider()
    if not project.get("responsable_bureau_email"):
        st.caption("⚠️ ResponsableBureauEmail manquant — impossible d'envoyer "
                   "pour approbation (voir migration).")
    elif st.button("📤 Envoyer pour approbation", key=f"send_{project['id']}"):
        try:
            send_for_approval(project)
            st.toast("Envoyé pour approbation ✅")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Échec de l'envoi pour approbation : {e}")
```

Note : `_render_text_panel` lit `project` via `select_project` ; les clés `brouillon_post`/`responsable_bureau_email` existent depuis Task 2.

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_dashboard_logic.py tests/test_dashboard_smoke.py -q`
Expected: PASS (le smoke test existant du dashboard reste vert).

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard_logic.py
git commit -m "feat: bouton Envoyer pour approbation (statut + notif Teams)"
```

---

### Task 8: Runbook de configuration Airtable + Graph

**Files:**
- Create: `docs/runbooks/2026-07-17-approbation-fondation.md`

**Interfaces:** aucune (documentation). Rassemble toute la config manuelle hors code.

- [ ] **Step 1: Écrire le runbook**

Créer `docs/runbooks/2026-07-17-approbation-fondation.md` avec ces sections :

```markdown
# Runbook — Fondation approbation (sous-projet A)

## 1. Champs Airtable à créer sur la table Projets
- `StatutPublication` — Single select : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`.
- `BrouillonPost`, `BrouillonDescFR`, `BrouillonDescEN` — Long text.
- `ResponsableBureauEmail` — Email.
- `ApprouvéPar` — Single line text.
- `DateApprobation` — Date.
- `RaisonRejet` — Long text.
- `LienPhotosSharePoint` — Formula : `CONCATENATE("<BASE_SHAREPOINT>/", {Project_No})`
  (remplacer `<BASE_SHAREPOINT>` par l'URL réelle du site SharePoint).

## 2. Automatisation d'entrée « À rédiger »
- Déclencheur : When record matches conditions.
- Conditions (toutes) : `StatutPublication` vide ET `BrouillonPost` vide ET
  `BrouillonDescFR` vide ET `BrouillonDescEN` vide ET `postDone` = false ET
  `confidential` = false.
- Action : Update record → `StatutPublication` = `À rédiger`.

## 3. Inscription d'app Azure AD (Microsoft Graph)
- Créer une app dans Azure AD (Entra) ; noter Tenant ID, Client ID, créer un Client secret.
- Permissions Graph : `Chat.Create`, `ChatMessage.Send` (application).
  ⚠️ L'envoi de messages de chat en application est une API protégée : suivre la
  demande d'accès Microsoft si nécessaire. Repli documenté (spec) : jeton délégué
  via compte de service, ou `Mail.Send` (e-mail Outlook portant le même lien).
- `GRAPH_SENDER_ID` : l'object id (GUID) de l'utilisateur/compte de service expéditeur.

## 4. Secrets à renseigner (.streamlit/secrets.toml ou variables d'env)
- `AIRTABLE_PAT`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`
- `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER_ID`
- `BASE_APP_URL` — URL publique de l'app Streamlit (pour construire `?record=`).

## 5. Migration des responsables
- Compléter `MAPPING` dans `migrate_responsable_email.py` (nom Airtable → email).
- Exécuter : `python migrate_responsable_email.py` ; traiter les noms non mappés listés.

## 6. Acceptation manuelle
1. Projet test non confidentiel, brouillons vides → passe auto à `À rédiger`.
2. Remplir les brouillons, sélectionner le projet dans le dashboard, cliquer
   « 📤 Envoyer pour approbation » → statut `En attente d'approbation` + le
   responsable reçoit un DM Teams avec le lien.
3. Ouvrir le lien → page d'approbation d'un seul brouillon (pas le dashboard).
4. Approuver → `Approuvé` + `ApprouvéPar` + `DateApprobation`.
5. Sur un autre : Rejeter avec motif → retour à `À rédiger` + `RaisonRejet`.
6. Un projet confidentiel ne passe jamais à `À rédiger`.
```

- [ ] **Step 2: Vérifier la suite complète + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (tous les tests, anciens et nouveaux).

```bash
git add docs/runbooks/2026-07-17-approbation-fondation.md
git commit -m "docs: runbook config Airtable + Graph pour l'approbation"
```

---

## Auto-revue du plan

- **Couverture du spec** :
  - Deux surfaces / routage `?record=` → Task 6. ✅
  - Modèle de données (8 champs + formule photos) → Tasks 1 (éditables), 2 (lecture), 8 (création réelle). ✅
  - Cycle de vie + rejet→À rédiger → Tasks 3 (payloads), 6 (page). ✅
  - Action « Envoyer pour approbation » → Task 7. ✅
  - Notification Teams / Graph + risque documenté → Tasks 4 et 8. ✅
  - Migration nom→email → Task 5. ✅
  - Automatisation d'entrée « À rédiger » → Task 8 (config Airtable). ✅
  - Streamlit conservé (aucune suppression) → aucun task de suppression. ✅
  - Tests des fonctions pures + acceptation manuelle → chaque task + Task 8. ✅
- **Placeholders** : `<BASE_SHAREPOINT>` et `MAPPING` vide sont des valeurs de config à remplir au runbook (documentées), pas des trous de code. Aucun « TODO » dans le code livré.
- **Cohérence des types** : `target_record_id`, `build_*_payload`, `build_approval_link`, `build_message`, `send_approval_request(recipient_email, html)`, `build_migration_updates → (updates, unmapped)`, `send_for_approval(project)` — signatures identiques entre définition (Tasks 3-5) et usage (Tasks 6-7).
```
