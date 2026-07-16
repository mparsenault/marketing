# Sous-projet A — Fondation Airtable + approbation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement the CODE tasks task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mettre en place dans Airtable le cycle de vie « brouillon → approbation → publié » et l'écran d'approbation du responsable bureau, et retirer l'app Streamlit devenue redondante.

**Architecture:** Airtable devient le pivot (état + UI d'approbation via une Interface native). Le dépôt ne garde qu'un client Airtable minimal (`airtable_client.py`) pour les scripts et les futurs sous-projets B/C. Un script migre `ResponsableBureau` (texte) vers `ResponsableBureauUser` (collaborateur) pour le routage des notifications.

**Tech Stack:** Python 3.9, requests, pytest (code) ; Airtable (champs, Interface, automatisations — configuration UI).

## ⚠️ Nature hybride de ce plan

Les tâches sont de deux types :
- **[CODE]** — implémentées dans le dépôt en TDD par un agent implémenteur (suite `pytest`).
- **[RUNBOOK]** — exécutées **par l'utilisateur dans l'UI Airtable** (les Interfaces et automatisations Airtable n'ont pas d'API publique, et le compte Airtable relié à Claude n'a pas accès à la base). Chaque étape RUNBOOK a un résultat observable à vérifier.

Ordre de dépendance : Task 1 [CODE] est indépendante. Task 2 [RUNBOOK] (champs + collaborateurs) doit précéder Task 3 [CODE] (migration, qui écrit dans les nouveaux champs) et Tasks 4-5 [RUNBOOK]. Task 6 [RUNBOOK] (acceptation) est la dernière.

## Global Constraints

- Noms/types de champs Airtable **exacts** (voir Task 2). Options de `StatutPublication` **exactes** : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`, `Rejeté`.
- Condition d'entrée « À rédiger » : `StatutPublication` vide **ET** `BrouillonPost` vide **ET** `BrouillonDescFR` vide **ET** `BrouillonDescEN` vide **ET** `postDone = false` **ET** `confidential = false`.
- **Ne jamais** écrire de brouillon non approuvé dans les champs live `descFR`/`descEN` (le site les lit). Les brouillons vivent dans `BrouillonDescFR`/`BrouillonDescEN` ; la recopie vers le live est en sous-projet C (hors périmètre).
- Créds Airtable lues depuis l'environnement (`AIRTABLE_PAT`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_NAME`). Base = `appScszc5IPkA58HX`, table = `Projets`.
- Une seule approbation couvre post + descriptions (pas d'approbation par canal).
- Commits en français, fin de message : `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1 [CODE] : Retrait de Streamlit + client Airtable env-only

Supprime toute l'app Streamlit (source, tests, fichiers miroirs, config, dépendances) et simplifie `airtable_client.get_config()` pour lire uniquement l'environnement.

**Files:**
- Delete: `app.py`, `dashboard.py`, `theme.py`, `transform.py`
- Delete: `tests/test_dashboard_logic.py`, `tests/test_dashboard_smoke.py`, `tests/test_theme.py`, `tests/test_transform.py`, `tests/test_app_gate.py`
- Delete (miroirs obsolètes trackés): `tests/dashboard.py`, `tests/theme.py`, `tests/transform.py`, `tests/app.py`, `tests/airtable_client.py`, `tests/README.md`, `tests/requirements.txt`
- Delete: `tests/conftest.py` (fixture de provisioning `secrets.toml` propre à AppTest), `.streamlit/config.toml`, `.streamlit/secrets.toml.example`
- Modify: `airtable_client.py` (`get_config`), `requirements.txt`, `README.md`
- Test: `tests/test_airtable_client.py` (ajout de tests `get_config`)
- Keep intact: `airtable_client.py` (sauf `get_config`), `tests/__init__.py`, `tests/test_airtable_client.py` (existant), `.streamlit/secrets.toml` (non tracké, créds locales)

**Interfaces:**
- Consumes: rien.
- Produces: `airtable_client.get_config() -> {"pat","base_id","table_name"}` lisant `os.environ` ; `fetch_projects`, `update_project`, `EDITABLE_FIELDS` inchangés (réutilisés par B/C).

- [ ] **Step 1: Écrire les tests get_config (env-only)**

Ajouter à la fin de `tests/test_airtable_client.py` :

```python
def test_get_config_reads_env(monkeypatch):
    monkeypatch.setenv("AIRTABLE_PAT", "patX")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "appScszc5IPkA58HX")
    monkeypatch.delenv("AIRTABLE_TABLE_NAME", raising=False)
    cfg = airtable_client.get_config()
    assert cfg == {"pat": "patX", "base_id": "appScszc5IPkA58HX",
                   "table_name": "Projets"}


def test_get_config_missing_raises(monkeypatch):
    monkeypatch.delenv("AIRTABLE_PAT", raising=False)
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    import pytest
    with pytest.raises(RuntimeError):
        airtable_client.get_config()
```

- [ ] **Step 2: Lancer les nouveaux tests (constat de départ)**

Run: `.venv/bin/python -m pytest tests/test_airtable_client.py -q`
Expected: `test_get_config_reads_env` peut échouer (la version actuelle lit `st.secrets` d'abord et renvoie potentiellement d'autres valeurs). On corrige au Step 3.

- [ ] **Step 3: Simplifier `get_config`**

Dans `airtable_client.py`, remplacer entièrement `get_config` (lignes 18-36) par :

```python
def get_config() -> dict:
    """Lit la config Airtable depuis les variables d'environnement."""
    pat = os.environ.get("AIRTABLE_PAT")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    table_name = os.environ.get("AIRTABLE_TABLE_NAME", "Projets")
    if not (pat and base_id):
        raise RuntimeError(
            "Config Airtable manquante : définir AIRTABLE_PAT et AIRTABLE_BASE_ID "
            "dans l'environnement."
        )
    return {"pat": pat, "base_id": base_id, "table_name": table_name}
```

- [ ] **Step 4: Supprimer les fichiers Streamlit**

```bash
cd /Users/marie-pierarsenault/Documents/GitHub/marketing
git rm app.py dashboard.py theme.py transform.py \
  tests/test_dashboard_logic.py tests/test_dashboard_smoke.py \
  tests/test_theme.py tests/test_transform.py tests/test_app_gate.py \
  tests/dashboard.py tests/theme.py tests/transform.py tests/app.py \
  tests/airtable_client.py tests/README.md tests/requirements.txt \
  tests/conftest.py .streamlit/config.toml .streamlit/secrets.toml.example
```

- [ ] **Step 5: Nettoyer `requirements.txt`**

Remplacer tout le contenu de `requirements.txt` par :

```
requests>=2.31
pytest>=8.0
```

- [ ] **Step 6: Réécrire `README.md`**

Remplacer tout le contenu de `README.md` par :

```markdown
# Marketing — publication des fiches projet

Workflow de publication des fiches projet à partir d'Airtable :
un agent (« Hermès », à venir) rédige les brouillons, le responsable bureau
approuve dans une Interface Airtable, puis publication sur réseaux + site.

Ce dépôt contient le client Airtable et les scripts de support.
Voir `docs/superpowers/specs/` et `docs/superpowers/plans/`.

## Configuration

Définir dans l'environnement :

```bash
export AIRTABLE_PAT=...          # PAT Airtable
export AIRTABLE_BASE_ID=appScszc5IPkA58HX
export AIRTABLE_TABLE_NAME=Projets
```

## Tests

```bash
.venv/bin/python -m pytest -q
```
```

- [ ] **Step 7: Lancer toute la suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — ne restent que les tests d'`airtable_client` (fetch, update, get_config). 0 échec.

- [ ] **Step 8: Vérifier qu'il ne reste aucune référence Streamlit**

Run: `grep -rn "streamlit\|import st\b\|st\." --include=*.py . | grep -v ".venv/"`
Expected: aucune sortie (rien dans le code du dépôt).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: retrait de l'app Streamlit, client Airtable env-only

Airtable devient le pivot (Interface d'approbation). On garde airtable_client
pour les scripts et les sous-projets B/C.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2 [RUNBOOK] : Créer les champs Airtable + inviter les collaborateurs

**Exécutée par l'utilisateur dans l'UI Airtable** (base `appScszc5IPkA58HX`, table `Projets`). Prérequis de Task 3, 4 et 5.

- [ ] **Step 1: Créer les 9 champs** (Table Projets → « + » pour chaque champ)

| Nom exact | Type Airtable | Configuration |
|---|---|---|
| `StatutPublication` | Single select | Options, dans cet ordre : `À rédiger`, `En attente d'approbation`, `Approuvé`, `Publié`, `Rejeté` |
| `BrouillonPost` | Long text | — |
| `BrouillonDescFR` | Long text | — |
| `BrouillonDescEN` | Long text | — |
| `ResponsableBureauUser` | User (collaborateur) | Autoriser 1 seul collaborateur |
| `ApprouvéPar` | User (collaborateur) | — |
| `DateApprobation` | Date | — |
| `RaisonRejet` | Long text | — |
| `LienPhotosSharePoint` | Formula | Formule = `CONCATENATE("<BASE_URL>", {Project_No})` (voir Step 3) |

Résultat attendu : les 9 champs apparaissent dans la table.

- [ ] **Step 2: Inviter les responsables bureau comme collaborateurs**

Pour chaque responsable bureau distinct : Partager la base → inviter son compte (email pro `@elem.global`) avec droit **Editor** (ou Commenter si suffisant pour l'Interface). Résultat attendu : ils apparaissent dans la liste des collaborateurs de la base.

- [ ] **Step 3: Déterminer `<BASE_URL>` SharePoint et finaliser la formule**

Un dossier SharePoint existe par `Project_No`. Récupérer l'URL de base du dossier parent (dans SharePoint : ouvrir le dossier d'un projet, copier l'URL, retirer le `Project_No` final pour obtenir le préfixe). Mettre à jour la formule `LienPhotosSharePoint` avec ce préfixe. Résultat attendu : sur un projet réel, cliquer le lien ouvre le bon dossier SharePoint.
(Note : l'assistant peut aider à confirmer le préfixe via les outils Microsoft 365 SharePoint si besoin.)

- [ ] **Step 4: Relever les identifiants utilisateurs Airtable**

Pour chaque responsable invité, récupérer son identifiant utilisateur Airtable (`usr...`). Méthode : dans l'API Airtable (Web API → base → users) ou via un enregistrement test où on l'assigne au champ `ResponsableBureauUser` puis on lit la valeur via l'API. Noter la correspondance `nom (tel qu'écrit dans ResponsableBureau) → usr...` — elle sert au Step de configuration de Task 3.

Résultat attendu : une liste `nom → usrXXXXXXXXXXXXXX` complète pour tous les responsables.

---

### Task 3 [CODE] : Script de migration ResponsableBureau → ResponsableBureauUser

Peuple le champ collaborateur depuis le texte, via une fonction pure testée + un script d'exécution. Dépend de Task 2 (champ créé + identifiants relevés).

**Files:**
- Create: `scripts/migrate_responsable_bureau.py`
- Modify: `airtable_client.py` (ajout de `update_record`)
- Test: `tests/test_migrate_responsable_bureau.py`, `tests/test_airtable_client.py` (ajout d'un test `update_record`)

**Interfaces:**
- Consumes (de Task 1) : `airtable_client.get_config`, `fetch_projects`.
- Produces:
  - `airtable_client.update_record(pat, base_id, table_name, record_id, fields: dict) -> None` — PATCH générique (sans filtre de champs), `typecast=True`.
  - `migrate_responsable_bureau.normalize_name(name: str) -> str`
  - `migrate_responsable_bureau.resolve_updates(records: list, name_to_user_id: dict) -> tuple[list, list]` — renvoie `(updates, unmapped)` ; `updates` = liste de `(record_id, user_id)` ; `unmapped` = liste de `(record_id, nom_brut)`.

- [ ] **Step 1: Écrire les tests de la fonction pure**

Créer `tests/test_migrate_responsable_bureau.py` :

```python
import importlib.util
import pathlib

# charge scripts/migrate_responsable_bureau.py comme module
_spec = importlib.util.spec_from_file_location(
    "migrate_rb",
    pathlib.Path(__file__).parent.parent / "scripts" / "migrate_responsable_bureau.py",
)
migrate_rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_rb)


def test_normalize_name_collapses_and_casefolds():
    assert migrate_rb.normalize_name("  Jean   Tremblay ") == "jean tremblay"
    assert migrate_rb.normalize_name("ÉLODIE") == "élodie".casefold()
    assert migrate_rb.normalize_name(None) == ""


def _rec(rid, name):
    return {"id": rid, "fields": {"ResponsableBureau": name}}


def test_resolve_updates_maps_known_names():
    records = [_rec("rec1", "Jean Tremblay"), _rec("rec2", "élodie")]
    mapping = {"jean tremblay": "usr111", migrate_rb.normalize_name("élodie"): "usr222"}
    updates, unmapped = migrate_rb.resolve_updates(records, mapping)
    assert updates == [("rec1", "usr111"), ("rec2", "usr222")]
    assert unmapped == []


def test_resolve_updates_reports_unmapped():
    records = [_rec("rec1", "Inconnu X")]
    updates, unmapped = migrate_rb.resolve_updates(records, {})
    assert updates == []
    assert unmapped == [("rec1", "Inconnu X")]


def test_resolve_updates_skips_empty_name():
    records = [_rec("rec1", ""), _rec("rec2", "   "), {"id": "rec3", "fields": {}}]
    updates, unmapped = migrate_rb.resolve_updates(records, {"x": "usr1"})
    assert updates == []
    assert unmapped == []
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `.venv/bin/python -m pytest tests/test_migrate_responsable_bureau.py -q`
Expected: FAIL — `scripts/migrate_responsable_bureau.py` n'existe pas encore.

- [ ] **Step 3: Écrire le script**

Créer `scripts/migrate_responsable_bureau.py` :

```python
"""Peuple ResponsableBureauUser (collaborateur) depuis ResponsableBureau (texte).

Usage : renseigner NAME_TO_USER_ID (voir Task 2, Step 4), définir les variables
d'environnement AIRTABLE_*, puis :  python scripts/migrate_responsable_bureau.py
"""

import sys

import airtable_client

# nom normalisé (via normalize_name) -> identifiant utilisateur Airtable "usr..."
# À COMPLÉTER depuis la correspondance relevée en Task 2, Step 4.
NAME_TO_USER_ID = {}


def normalize_name(name: str) -> str:
    return " ".join((name or "").split()).casefold()


def resolve_updates(records: list, name_to_user_id: dict):
    updates, unmapped = [], []
    for rec in records:
        rid = rec.get("id", "")
        raw = (rec.get("fields", {}).get("ResponsableBureau") or "").strip()
        if not raw:
            continue
        uid = name_to_user_id.get(normalize_name(raw))
        if uid:
            updates.append((rid, uid))
        else:
            unmapped.append((rid, raw))
    return updates, unmapped


def main() -> None:
    cfg = airtable_client.get_config()
    records = airtable_client.fetch_projects(**cfg)
    updates, unmapped = resolve_updates(records, NAME_TO_USER_ID)
    for rid, uid in updates:
        airtable_client.update_record(
            cfg["pat"], cfg["base_id"], cfg["table_name"], rid,
            {"ResponsableBureauUser": {"id": uid}},
        )
        print(f"OK {rid} -> {uid}")
    for rid, raw in unmapped:
        print(f"NON MAPPÉ {rid}: {raw!r}", file=sys.stderr)
    print(f"\n{len(updates)} mis à jour, {len(unmapped)} non mappés")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ajouter `update_record` à `airtable_client.py`**

Après `update_project`, ajouter :

```python
def update_record(pat: str, base_id: str, table_name: str,
                  record_id: str, fields: dict) -> None:
    """PATCH générique d'un enregistrement (sans filtre de champs)."""
    body = {"records": [{"id": record_id, "fields": fields}], "typecast": True}
    r = requests.patch(
        _table_url(base_id, table_name),
        headers=_headers(pat),
        json=body,
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
```

- [ ] **Step 5: Ajouter le test de `update_record`**

Ajouter à `tests/test_airtable_client.py` :

```python
def test_update_record_sends_fields_unfiltered(monkeypatch):
    captured = {}

    def fake_patch(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResp({"records": [{"id": "rec1"}]})

    monkeypatch.setattr(airtable_client.requests, "patch", fake_patch)
    airtable_client.update_record(
        "patX", "appScszc5IPkA58HX", "Projets", "rec1",
        {"ResponsableBureauUser": {"id": "usr111"}},
    )
    sent = captured["json"]["records"][0]
    assert sent["id"] == "rec1"
    assert sent["fields"] == {"ResponsableBureauUser": {"id": "usr111"}}
    assert captured["json"]["typecast"] is True
```

- [ ] **Step 6: Lancer toute la suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (fonction pure de migration + `update_record` + tests existants).

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_responsable_bureau.py airtable_client.py tests/test_migrate_responsable_bureau.py tests/test_airtable_client.py
git commit -m "feat: script de migration ResponsableBureau -> collaborateur + update_record

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 8: Exécution de la migration (utilisateur)**

Compléter `NAME_TO_USER_ID` dans le script avec la correspondance de Task 2 Step 4, exporter les variables `AIRTABLE_*`, puis :
Run: `.venv/bin/python scripts/migrate_responsable_bureau.py`
Expected: lignes `OK rec... -> usr...` ; les éventuels `NON MAPPÉ` sont traités manuellement (compléter le mapping et relancer). Vérifier dans Airtable que `ResponsableBureauUser` est peuplé.

---

### Task 4 [RUNBOOK] : Automatisation « À rédiger » (amorçage du pipeline)

**Exécutée par l'utilisateur dans l'UI Airtable** (Automations). Dépend de Task 2.

- [ ] **Step 1: Créer l'automatisation d'amorçage**

Automations → New automation.
- **Trigger** : « When a record matches conditions », table Projets, conditions (toutes) :
  `StatutPublication` est vide **ET** `BrouillonPost` est vide **ET** `BrouillonDescFR` est vide **ET** `BrouillonDescEN` est vide **ET** `postDone` est décoché **ET** `confidential` est décoché.
- **Action** : « Update record » (l'enregistrement déclencheur) → `StatutPublication = À rédiger`.

- [ ] **Step 2: Vérifier**

Créer/éditer un projet test non confidentiel, sans brouillon ni post → il doit passer à `À rédiger`. Marquer un projet `confidential` → il ne doit **pas** passer à `À rédiger`. Résultat attendu : statut correct dans les deux cas.

---

### Task 5 [RUNBOOK] : Interface d'approbation + notification email

**Exécutée par l'utilisateur dans l'UI Airtable** (Interfaces + Automations). Dépend de Task 2 et Task 3 (routage peuplé).

- [ ] **Step 1: Créer l'Interface « Brouillons à approuver »**

Interfaces → New interface → page de type **List** (ou Record review), source = table Projets.
- **Filtre de la page** : `StatutPublication = En attente d'approbation` **ET** `ResponsableBureauUser = Current user`.
- **Champs affichés** (détail) : `Project_No`, `NomDuProjet`, `Entreprise`, `Client`, `BrouillonPost`, `BrouillonDescFR`, `BrouillonDescEN`, `LienPhotosSharePoint`.

- [ ] **Step 2: Ajouter les boutons d'action**

- Bouton **Approuver** → action « Update record » : `StatutPublication = Approuvé`, `ApprouvéPar = Current user`, `DateApprobation = Today`.
- Bouton **Rejeter** → action qui passe `StatutPublication = Rejeté` et ouvre la saisie de `RaisonRejet` (via un formulaire d'édition sur le champ, ou une action Update avec champ éditable).

- [ ] **Step 3: Créer l'automatisation de notification**

Automations → New automation.
- **Trigger** : « When record matches conditions » → `StatutPublication = En attente d'approbation`.
- **Action** : « Send email » au `ResponsableBureauUser` du projet, sujet incluant `Project_No` + `NomDuProjet`, corps incluant un extrait de `BrouillonPost` et le lien vers l'Interface d'approbation.

- [ ] **Step 4: Vérifier**

Voir Task 6.

---

### Task 6 [RUNBOOK] : Acceptation manuelle de bout en bout

**Exécutée par l'utilisateur.** Valide toute la fondation.

- [ ] **Step 1: Parcours nominal**

Sur un projet test non confidentiel avec un `ResponsableBureauUser` A :
1. Vérifier passage auto à `À rédiger`.
2. Remplir `BrouillonPost`, `BrouillonDescFR`, `BrouillonDescEN` et passer `StatutPublication = En attente d'approbation`.
3. Vérifier que A reçoit l'email de notification.
4. Se connecter en tant que A → l'Interface montre le projet ; se connecter en tant qu'un autre responsable B → le projet **n'apparaît pas**.
5. En tant que A, cliquer **Approuver** → `StatutPublication = Approuvé`, `ApprouvéPar = A`, `DateApprobation` = aujourd'hui.

- [ ] **Step 2: Parcours rejet**

Sur un autre projet en `En attente d'approbation`, cliquer **Rejeter**, saisir une `RaisonRejet` → `StatutPublication = Rejeté` et `RaisonRejet` enregistrée.

- [ ] **Step 3: Garde confidentialité**

Vérifier qu'un projet `confidential = true` ne passe jamais à `À rédiger`.

Résultat attendu : les 3 parcours se comportent comme décrit. La fondation est prête pour le sous-projet B (Hermès).

## Self-Review (couverture du spec)

- Champs (9) → Task 2 Step 1 ✓
- Séparation brouillon/live → champs Brouillon* + note « hors périmètre C » ✓
- Cycle de vie + condition « À rédiger » → Task 4 ✓
- Interface d'approbation (filtre par current user, champs, boutons) → Task 5 Steps 1-2 ✓
- Notification email → Task 5 Step 3 ✓
- Migration ResponsableBureau → collaborateur → Task 3 ✓
- Lien photos SharePoint (formule, 1 dossier/Project_No) → Task 2 Steps 1,3 ✓
- Retrait de Streamlit + airtable_client conservé/allégé → Task 1 ✓
- Acceptation → Task 6 ✓
