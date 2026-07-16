"""UI Streamlit de l'onglet Projets : stats, filtres, tableau, édition."""

from datetime import date

import pandas as pd
import streamlit as st

import airtable_client
import theme
import transform


@st.cache_data(ttl=60)
def load_projects():
    cfg = airtable_client.get_config()
    records = airtable_client.fetch_projects(**cfg)
    return [transform.record_to_project(r) for r in records]


def _dot(value: bool) -> str:
    return "🟢" if value else "🔴"


def _build_dataframe(projects: list) -> pd.DataFrame:
    rows = []
    for p in projects:
        pres = theme.get_confidential_presentation(
            p["confidential"], p["confidential_reason"]
        )
        rows.append({
            "🔒": pres["icon"],
            "No": p["project_no"],
            "Compagnie": p["company"],
            "Projet": p["project"] or f"Projet #{p['project_no']}",
            "Client": p["client"],
            "Dates": p["dates"],
            "Resp. bureau": p["responsable_bureau"] or "—",
            "Resp. chantier": p["responsable_chantier"] or "—",
            "📷": _dot(p["photo_available"]),
            "🌐": _dot(p["online"]),
            "📱": _dot(p["post_done"]),
        })
    return pd.DataFrame(rows)


def _style_dataframe(df: pd.DataFrame, projects: list):
    def row_style(row):
        p = projects[row.name]
        color = theme.get_company_color(p["company"])
        styles = [""] * len(row)
        # Griser toute la ligne si confidentiel
        if p["confidential"]:
            styles = ["background-color: rgba(0,0,0,0.05); opacity: 0.55"] * len(row)
        # Couleur de compagnie sur la cellule "Compagnie"
        comp_idx = list(row.index).index("Compagnie")
        styles[comp_idx] = f"background-color: {color}; color: white; font-weight: 600"
        return styles

    return df.style.apply(row_style, axis=1)


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


def _render_edit_panel(project: dict):
    st.divider()
    st.subheader(f"✏️ Édition — {project['project'] or project['project_no']}")
    with st.form(key=f"edit_{project['id']}"):
        c1, c2, c3 = st.columns(3)
        photo = c1.checkbox("📷 Photo dispo", value=project["photo_available"])
        online = c2.checkbox("🌐 En ligne", value=project["online"])
        post = c3.checkbox("📱 Post fait", value=project["post_done"])

        conf = st.checkbox("🔒 Confidentiel (non-publiable)", value=project["confidential"])
        reason = st.text_input("Raison", value=project["confidential_reason"])
        notes = st.text_area("Notes", value=project["notes"])
        desc_en = st.text_area("Description (EN)", value=project["desc_en"])

        submitted = st.form_submit_button("💾 Enregistrer", type="primary")

    if submitted:
        cfg = airtable_client.get_config()
        try:
            payload = build_edit_payload(photo, online, post, conf, reason, notes, desc_en)
            airtable_client.update_project(
                cfg["pat"], cfg["base_id"], cfg["table_name"], project["id"],
                payload,
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
    event = st.dataframe(
        _style_dataframe(df, filtered),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"projects_table_{sig}",
    )

    selected_rows = event.selection.rows if event and event.selection else []
    project = select_project(filtered, selected_rows)
    if project is not None:
        _render_edit_panel(project)
