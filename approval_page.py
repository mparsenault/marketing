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
