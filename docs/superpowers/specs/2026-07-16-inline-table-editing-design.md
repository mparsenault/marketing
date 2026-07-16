# Édition inline du tableau des projets — Design

Date : 2026-07-16

## Contexte

Aujourd'hui, l'édition d'un projet se fait ainsi (`dashboard.py`) :
1. L'utilisateur clique une ligne du tableau `st.dataframe` (sélection mono-ligne).
2. Un panneau `_render_edit_panel` s'ouvre **en dessous** avec un formulaire
   (4 cases à cocher + 3 champs texte) et un bouton « Enregistrer ».

Problèmes signalés par l'utilisatrice :
- Le panneau est en dessous → il faut scroller, c'est loin du tableau.
- On ne peut éditer qu'**un seul** projet à la fois.
- Pas d'**édition directe** dans les cellules.

## Objectif

Permettre l'édition directe des statuts (cases à cocher) **dans les cellules du
tableau**, sur plusieurs projets à la suite, avec sauvegarde automatique. Garder
l'édition des champs texte dans un panneau léger.

## Approche retenue : édition hybride

### 1. Tableau éditable — `st.data_editor`

Remplacer `st.dataframe` par `st.data_editor`.

- **Colonnes éditables** (cases à cocher, `st.column_config.CheckboxColumn`) :
  `📷` (photoAvailable), `🌐` (online), `📱` (postDone), `🔒` (confidential).
  Les valeurs de ces colonnes deviennent des `bool` (plus des emojis 🟢/🔴).
- **Colonnes en lecture seule** (via `disabled=[...]`) : `No`, `Compagnie`,
  `Projet`, `Client`, `Dates`, `Resp. bureau`, `Resp. chantier`.
- La colonne icône `🔒` de présentation (dérivée) est **supprimée** : la case à
  cocher `🔒` éditable la remplace.

### 2. Auto-sauvegarde

`st.data_editor` reçoit un callback `on_change`. Streamlit stocke le delta des
modifications dans `st.session_state[<editor_key>]["edited_rows"]`, sous la forme
`{row_position: {col_label: new_value}}`.

Le callback :
1. Lit `edited_rows` depuis `st.session_state`.
2. Convertit le delta en une liste de `(record_id, payload)` via
   `compute_inline_updates(edited_rows, filtered)` — **fonction pure et testable**.
   - Mappe le libellé de colonne → champ Airtable
     (`📷`→`photoAvailable`, `🌐`→`online`, `📱`→`postDone`, `🔒`→`confidential`).
   - N'inclut **que les champs modifiés** (PATCH partiel).
   - Si `confidential` passe à `False`, ajoute aussi `confidentialReason: ""` au
     payload (cohérent avec la logique existante).
3. Envoie un `PATCH` par projet modifié via `airtable_client.update_project`
   (qui filtre déjà sur `EDITABLE_FIELDS`).
4. `st.cache_data.clear()` puis rerun naturel → `load_projects` recharge les
   données fraîches. Le delta de `data_editor` se réinitialise car les données
   d'entrée reflètent désormais la modification.
5. En cas d'erreur, message d'erreur non bloquant (les autres updates passent).

### 3. Panneau texte via `selectbox`

`st.data_editor` **ne gère pas** la sélection de ligne par clic
(`on_select`/`selection_mode` sont propres à `st.dataframe`). Pour éditer les
champs texte :

- Un `st.selectbox` « ✏️ Notes & description — choisir un projet » liste les
  projets filtrés (option vide par défaut = panneau fermé).
- À la sélection, un petit `st.form` affiche : `Raison` (confidentialité),
  `Notes`, `Description (EN)` + bouton « Enregistrer ».
- Sauvegarde explicite via `build_text_payload(notes, desc_en, reason)` —
  **fonction pure** renvoyant `{"notes", "descEN", "confidentialReason"}`.
- La case `🔒 Confidentiel` n'est **pas** dans ce panneau : elle s'édite inline.

### 4. Style couleur — abandonné

`st.data_editor` ne supporte pas la coloration de cellules (`pandas.Styler`). On
perd donc :
- la couleur de compagnie sur la cellule « Compagnie » → **texte simple** (décision) ;
- le grisage des lignes confidentielles → le statut reste visible via la case `🔒`.

`_style_dataframe` et son usage sont supprimés. `theme.get_company_color` /
`get_confidential_presentation` ne sont plus appelés par le tableau (on peut les
laisser dans `theme.py`, ils restent testés).

## Découpage / interfaces

Fonctions pures (dans `dashboard.py`, testables sans Streamlit) :

- `compute_inline_updates(edited_rows: dict, filtered: list) -> list[tuple[str, dict]]`
- `build_text_payload(notes: str, desc_en: str, reason: str) -> dict`
- `select_project(filtered, selected_rows)` — conservée, réutilisée pour mapper
  l'index du `selectbox` vers le projet.

Fonctions UI (effets Streamlit) :

- `_build_dataframe` — adaptée : booléens en `bool`, colonne `Compagnie` en texte,
  suppression de la colonne icône `🔒`.
- `_on_inline_edit(editor_key, filtered)` — le callback d'auto-sauvegarde.
- `_render_text_panel(filtered)` — remplace `_render_edit_panel`.
- `render()` — utilise `st.data_editor` + `column_config` + `disabled` + `on_change`.

Le mapping libellé→champ est une constante partagée
(`INLINE_COLUMN_TO_FIELD`) pour éviter la duplication entre `_build_dataframe`,
la config des colonnes et `compute_inline_updates`.

## Gestion d'erreurs

- Échec de chargement Airtable : inchangé (`st.error` + `st.stop`).
- Échec d'un `PATCH` inline : on capture par projet, on continue les autres, et on
  affiche un `st.error`/`st.toast` récapitulatif. Le cache est quand même vidé.
- `compute_inline_updates` ignore les lignes hors intervalle (index invalide) sans
  planter (robustesse identique à `select_project`).

## Tests

- `compute_inline_updates` : delta vide → `[]` ; une case modifiée → un payload à
  un champ ; `confidential=False` → payload inclut `confidentialReason: ""` ;
  index de ligne hors intervalle → ignoré ; plusieurs lignes → plusieurs updates.
- `build_text_payload` : renvoie exactement `{"notes", "descEN", "confidentialReason"}`.
- `select_project` : tests existants conservés.
- Smoke test : mettre à jour `test_dashboard_smoke.py` — le tableau est maintenant
  `at.data_editor` (plus `at.dataframe`). Vérifier `len(at.data_editor) == 1` et
  que les 4 cartes de stats sont présentes.
- `test_build_edit_payload_*` : **supprimés**. `build_edit_payload` (qui envoyait
  les 7 champs d'un coup) est retiré, remplacé par `build_text_payload` (3 champs
  texte) + `compute_inline_updates` (les 4 booléens), chacun avec ses tests.

## Hors périmètre (YAGNI)

- Pas d'ajout/suppression de lignes dans le tableau (`num_rows="fixed"`).
- Pas d'édition inline des champs texte (choix hybride assumé).
- Pas de préservation de la couleur de compagnie (choix « texte simple »).
