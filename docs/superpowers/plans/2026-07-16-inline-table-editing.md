# Édition inline du tableau — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre l'édition directe des 4 statuts (📷 🌐 📱 🔒) dans les cellules du tableau avec auto-sauvegarde, et déplacer l'édition des champs texte dans un panneau ouvert via un `selectbox`.

**Architecture:** Remplacer `st.dataframe` (lecture seule + panneau de clic) par `st.data_editor` avec colonnes cases à cocher éditables et un callback `on_change` qui envoie un PATCH Airtable partiel par champ modifié. Les champs texte passent dans un panneau distinct sélectionné par `selectbox`. La logique de conversion delta→payload est extraite en fonctions pures testables.

**Tech Stack:** Python 3.9, Streamlit 1.50, pandas, requests, pytest, `streamlit.testing.v1.AppTest`.

## Global Constraints

- Streamlit ≥ 1.42 (installé : 1.50.0) ; pandas ≥ 2.0 ; requests ≥ 2.31.
- Toute écriture Airtable passe par `airtable_client.update_project`, qui filtre sur `airtable_client.EDITABLE_FIELDS` et envoie `typecast=True`.
- Champs Airtable éditables : `photoAvailable`, `online`, `postDone`, `confidential`, `confidentialReason`, `notes`, `descEN`.
- Aucune logique métier dans `airtable_client.py` (couche HTTP uniquement).
- Commentaires et libellés UI en français, cohérents avec le code existant.
- Les fonctions pures ne doivent PAS importer/appeler Streamlit.

---

### Task 1: Fonctions pures — mapping delta et payload texte

Remplace `build_edit_payload` (qui envoyait les 7 champs d'un coup) par deux fonctions pures : `compute_inline_updates` (delta des cases → liste de PATCH) et `build_text_payload` (3 champs texte). Ajoute la constante partagée `INLINE_COLUMN_TO_FIELD`.

**Files:**
- Modify: `dashboard.py` (supprimer `build_edit_payload`, lignes 112-124 ; ajouter la constante + 2 fonctions)
- Test: `tests/test_dashboard_logic.py` (supprimer les 3 tests `test_build_edit_payload_*`, lignes 29-56 ; ajouter les nouveaux tests)

**Interfaces:**
- Consumes: rien (fonctions pures).
- Produces:
  - `INLINE_COLUMN_TO_FIELD: dict[str, str]` = `{"📷": "photoAvailable", "🌐": "online", "📱": "postDone", "🔒": "confidential"}`
  - `compute_inline_updates(edited_rows: dict, filtered: list) -> list[tuple[str, dict]]` — chaque tuple est `(record_id, payload)` ; payload ne contient que les champs modifiés ; si `confidential` passe à `False`, ajoute `"confidentialReason": ""` ; ignore les index de ligne hors intervalle et les colonnes inconnues.
  - `build_text_payload(notes: str, desc_en: str, reason: str) -> dict` = `{"notes": notes, "descEN": desc_en, "confidentialReason": reason}`

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_dashboard_logic.py`, remplacer le bloc `# --- build_edit_payload ---` et ses 3 tests (lignes 29-56) par :

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv/bin/python -m pytest tests/test_dashboard_logic.py -q`
Expected: FAIL — `AttributeError: module 'dashboard' has no attribute 'compute_inline_updates'`

- [ ] **Step 3: Implémenter les fonctions**

Dans `dashboard.py`, supprimer entièrement `build_edit_payload` (lignes 112-124) et insérer à sa place :

```python
INLINE_COLUMN_TO_FIELD = {
    "📷": "photoAvailable",
    "🌐": "online",
    "📱": "postDone",
    "🔒": "confidential",
}


def compute_inline_updates(edited_rows: dict, filtered: list) -> list:
    """Convertit le delta de st.data_editor en liste de (record_id, payload).

    edited_rows : {position_ligne: {libellé_colonne: nouvelle_valeur}}.
    N'inclut que les champs modifiés ; vide confidentialReason quand
    confidential repasse à False ; ignore les index hors intervalle et les
    colonnes non éditables."""
    updates = []
    for row_key, changes in edited_rows.items():
        idx = int(row_key)
        if idx < 0 or idx >= len(filtered):
            continue
        payload = {}
        for col, value in changes.items():
            field = INLINE_COLUMN_TO_FIELD.get(col)
            if field is None:
                continue
            payload[field] = value
            if field == "confidential" and value is False:
                payload["confidentialReason"] = ""
        if payload:
            updates.append((filtered[idx]["id"], payload))
    return updates


def build_text_payload(notes: str, desc_en: str, reason: str) -> dict:
    """Payload PATCH du panneau texte (Notes, Description EN, Raison)."""
    return {"notes": notes, "descEN": desc_en, "confidentialReason": reason}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv/bin/python -m pytest tests/test_dashboard_logic.py -q`
Expected: PASS (tests `select_project` + `compute_inline_updates` + `build_text_payload`)

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard_logic.py
git commit -m "feat: fonctions pures pour édition inline (compute_inline_updates, build_text_payload)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: UI — data_editor éditable, auto-sauvegarde, panneau texte

Remplace le rendu lecture-seule + panneau-au-clic par `st.data_editor` (cases éditables, auto-save via `on_change`) et un panneau texte sélectionné par `selectbox`. Supprime le style couleur (`_style_dataframe`).

**Files:**
- Modify: `dashboard.py` (`_build_dataframe`, suppression de `_style_dataframe`, remplacement de `_render_edit_panel` par `_render_text_panel`, ajout de `_on_inline_edit`, réécriture de `render`)
- Test: `tests/test_dashboard_smoke.py` (le tableau devient `at.data_editor`)

**Interfaces:**
- Consumes (de Task 1) : `INLINE_COLUMN_TO_FIELD`, `compute_inline_updates(edited_rows, filtered)`, `build_text_payload(notes, desc_en, reason)`, ainsi que `select_project(filtered, selected_rows)` (existante).
- Produces :
  - `_build_dataframe(projects: list) -> pd.DataFrame` — colonnes `No, Compagnie, Projet, Client, Dates, Resp. bureau, Resp. chantier` (texte) + `📷, 🌐, 📱, 🔒` (bool). Plus de colonne icône dérivée, plus de style.
  - `_on_inline_edit(editor_key: str, filtered: list) -> None` — callback `on_change`.
  - `_render_text_panel(filtered: list) -> None`.

- [ ] **Step 1: Mettre à jour le smoke test (test qui échoue)**

Dans `tests/test_dashboard_smoke.py`, remplacer les 2 dernières assertions (lignes 34-35) :

```python
    # Le tableau éditable est rendu
    assert len(at.data_editor) == 1
```

- [ ] **Step 2: Lancer le smoke test pour vérifier qu'il échoue**

Run: `.venv/bin/python -m pytest tests/test_dashboard_smoke.py -q`
Expected: FAIL — `at.data_editor` vide (le code rend encore `st.dataframe`), `assert len([]) == 1`.

- [ ] **Step 3: Réécrire `_build_dataframe`**

Dans `dashboard.py`, remplacer `_build_dataframe` (lignes 24-43) par :

```python
def _build_dataframe(projects: list) -> pd.DataFrame:
    rows = []
    for p in projects:
        rows.append({
            "No": p["project_no"],
            "Compagnie": p["company"],
            "Projet": p["project"] or f"Projet #{p['project_no']}",
            "Client": p["client"],
            "Dates": p["dates"],
            "Resp. bureau": p["responsable_bureau"] or "—",
            "Resp. chantier": p["responsable_chantier"] or "—",
            "📷": p["photo_available"],
            "🌐": p["online"],
            "📱": p["post_done"],
            "🔒": p["confidential"],
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Supprimer `_style_dataframe` et `_dot`**

Dans `dashboard.py`, supprimer entièrement la fonction `_style_dataframe` (anciennes lignes 46-59) et la fonction `_dot` (anciennes lignes 20-21) — elles ne sont plus utilisées. Retirer aussi l'import `theme` s'il n'est plus référencé ailleurs dans le fichier (vérifier avec `grep -n "theme\." dashboard.py` ; ne retirer l'import que si aucune occurrence ne subsiste).

- [ ] **Step 5: Ajouter le callback `_on_inline_edit`**

Dans `dashboard.py`, ajouter (au-dessus de `_render_text_panel`) :

```python
def _on_inline_edit(editor_key: str, filtered: list) -> None:
    """Callback on_change : envoie un PATCH Airtable par champ modifié.

    Le message de résultat est stocké en session_state puis affiché dans
    render() (les commandes d'affichage sont peu fiables dans un callback)."""
    state = st.session_state.get(editor_key, {})
    updates = compute_inline_updates(state.get("edited_rows", {}), filtered)
    if not updates:
        return
    cfg = airtable_client.get_config()
    errors = []
    for rec_id, payload in updates:
        try:
            airtable_client.update_project(
                cfg["pat"], cfg["base_id"], cfg["table_name"], rec_id, payload,
            )
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
    st.cache_data.clear()
    if errors:
        st.session_state["_inline_edit_msg"] = ("error", " ; ".join(errors))
    else:
        st.session_state["_inline_edit_msg"] = ("ok", "Modifications enregistrées ✅")
```

- [ ] **Step 6: Remplacer `_render_edit_panel` par `_render_text_panel`**

Dans `dashboard.py`, supprimer entièrement `_render_edit_panel` (anciennes lignes 127-155) et insérer :

```python
def _render_text_panel(filtered: list) -> None:
    st.divider()
    labels = ["— Choisir un projet —"] + [
        f"{p['project'] or ('Projet #' + str(p['project_no']))} ({p['project_no']})"
        for p in filtered
    ]
    choice = st.selectbox(
        "✏️ Notes & description — choisir un projet",
        range(len(labels)),
        format_func=lambda i: labels[i],
    )
    project = select_project(filtered, [choice - 1]) if choice else None
    if project is None:
        return

    st.subheader(f"✏️ Édition — {project['project'] or project['project_no']}")
    with st.form(key=f"text_{project['id']}"):
        reason = st.text_input("Raison (confidentialité)",
                               value=project["confidential_reason"])
        notes = st.text_area("Notes", value=project["notes"])
        desc_en = st.text_area("Description (EN)", value=project["desc_en"])
        submitted = st.form_submit_button("💾 Enregistrer", type="primary")

    if submitted:
        cfg = airtable_client.get_config()
        try:
            payload = build_text_payload(notes, desc_en, reason)
            airtable_client.update_project(
                cfg["pat"], cfg["base_id"], cfg["table_name"], project["id"], payload,
            )
            st.cache_data.clear()
            st.toast("Projet enregistré ✅")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Erreur d'enregistrement : {e}")
```

- [ ] **Step 7: Réécrire la fin de `render`**

Dans `dashboard.py`, dans `render`, juste après `top[2]`/`st.logout()` (avant `try: all_loaded = load_projects()`), insérer l'affichage du message en attente :

```python
    msg = st.session_state.pop("_inline_edit_msg", None)
    if msg:
        kind, text = msg
        if kind == "ok":
            st.toast(text)
        else:
            st.error(f"Erreur d'enregistrement : {text}")
```

Puis remplacer le bloc de rendu du tableau + panneau (anciennes lignes 193-208, du `df = _build_dataframe(filtered)` jusqu'à la fin) par :

```python
    df = _build_dataframe(filtered)
    sig = hash((filters["search"], filters["company"], filters["year_from"], filters["year_to"],
                filters["without_photo"], filters["without_online"], filters["without_post"]))
    editor_key = f"projects_editor_{sig}"
    st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key=editor_key,
        disabled=["No", "Compagnie", "Projet", "Client", "Dates",
                  "Resp. bureau", "Resp. chantier"],
        column_config={
            "📷": st.column_config.CheckboxColumn("📷", help="Photo dispo"),
            "🌐": st.column_config.CheckboxColumn("🌐", help="En ligne"),
            "📱": st.column_config.CheckboxColumn("📱", help="Post fait"),
            "🔒": st.column_config.CheckboxColumn("🔒", help="Confidentiel"),
        },
        on_change=_on_inline_edit,
        args=(editor_key, filtered),
    )

    _render_text_panel(filtered)
```

- [ ] **Step 8: Lancer toute la suite de tests**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 0 échec (le smoke test voit `at.data_editor`, la logique pure passe, `airtable_client` inchangé).

- [ ] **Step 9: Vérification manuelle rapide (fumée d'import)**

Run: `.venv/bin/python -c "import ast; ast.parse(open('dashboard.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 10: Commit**

```bash
git add dashboard.py tests/test_dashboard_smoke.py
git commit -m "feat: édition inline des statuts dans le tableau + panneau texte

- st.dataframe -> st.data_editor avec cases à cocher éditables (📷🌐📱🔒)
- auto-sauvegarde via callback on_change (PATCH partiel)
- champs texte (Notes/Description/Raison) via selectbox + formulaire
- suppression du style couleur (non supporté par data_editor)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes de vérification post-implémentation (hors TDD)

À faire tourner manuellement une fois les tâches finies (`streamlit run app.py`) :
- Cocher une case → toast « Modifications enregistrées », valeur persistée dans Airtable après rechargement.
- Cocher plusieurs cases sur plusieurs lignes → chaque changement part.
- Décocher 🔒 → la raison est vidée dans Airtable.
- Sélectionner un projet dans le selectbox → éditer Notes/Description → « Enregistrer » persiste.
- Changer un filtre après une édition → pas d'erreur, pas de ré-application fantôme du delta.
