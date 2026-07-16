"""UI Streamlit de l'onglet Projets : stats, filtres, tableau, édition."""

from datetime import date

import pandas as pd
import streamlit as st

import airtable_client
import transform


@st.cache_data(ttl=60)
def load_projects():
    cfg = airtable_client.get_config()
    records = airtable_client.fetch_projects(**cfg)
    return [transform.record_to_project(r) for r in records]


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


def _render_stats(stats: dict):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📁 Total projets", stats["total"])
    c2.metric("📷 Photos dispo", stats["photos"])
    c3.metric("🌐 En ligne", stats["online"])
    c4.metric("✍️ Posts à faire", stats["todo"])


def _render_filters(all_projects: list) -> dict:
    companies = transform.company_options(all_projects)
    years = transform.year_options(all_projects)
    year_labels = [""] + [str(y) for y in years]

    row1 = st.columns([3, 2, 1, 1])
    search = row1[0].text_input("Rechercher", placeholder="Projet, client, ville…",
                                label_visibility="collapsed")
    company = row1[1].selectbox("Compagnie", [""] + companies,
                                format_func=lambda c: c or "Toutes les entreprises",
                                label_visibility="collapsed")
    year_from = row1[2].selectbox("Depuis", year_labels,
                                  format_func=lambda y: y or "Depuis…",
                                  label_visibility="collapsed")
    year_to = row1[3].selectbox("Jusqu'à", year_labels,
                                format_func=lambda y: y or "Jusqu'à…",
                                label_visibility="collapsed")

    row2 = st.columns(3)
    without_photo = row2[0].toggle("📷 Sans photo dispo")
    without_online = row2[1].toggle("🌐 Pas sur le site")
    without_post = row2[2].toggle("📱 Sans post réseaux")

    return {
        "search": search, "company": company,
        "year_from": year_from, "year_to": year_to,
        "without_photo": without_photo, "without_online": without_online,
        "without_post": without_post,
    }


def select_project(filtered: list, selected_rows: list):
    """Return the selected project, or None if there is no valid in-range selection.
    Guards against a stale selection index that outlives a filter change."""
    if not selected_rows:
        return None
    idx = selected_rows[0]
    if idx < 0 or idx >= len(filtered):
        return None
    return filtered[idx]


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


def render():
    # En-tête utilisateur + déconnexion
    top = st.columns([6, 2, 1])
    top[0].title("📁 Projets")
    user_name = getattr(st.user, "name", None) or getattr(st.user, "email", "")
    if user_name:
        top[1].caption(f"👤 {user_name}")
    if top[2].button("Se déconnecter"):
        st.logout()

    msg = st.session_state.pop("_inline_edit_msg", None)
    if msg:
        kind, text = msg
        if kind == "ok":
            st.toast(text)
        else:
            st.error(f"Erreur d'enregistrement : {text}")

    try:
        all_loaded = load_projects()
    except Exception as e:  # noqa: BLE001
        st.error(f"Impossible de charger les projets depuis Airtable : {e}")
        st.stop()

    all_projects = transform.filter_recent(all_loaded, date.today().year)

    _render_stats(transform.compute_stats(all_projects))

    filters = _render_filters(all_projects)
    filtered = transform.sort_by_end_date_desc(
        transform.apply_filters(all_projects, filters)
    )

    st.caption(
        f"Tous les {len(all_projects)} projets"
        if len(filtered) == len(all_projects)
        else f"{len(filtered)} projets affichés / {len(all_projects)}"
    )

    if not filtered:
        st.info("📭 Aucun projet trouvé. Modifiez vos filtres pour voir plus de projets.")
        return

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
