import streamlit as st

st.set_page_config(
    page_title="Dashboard Marketing — Projets",
    page_icon="📁",
    layout="wide",
)


def main():
    if not st.user.is_logged_in:
        st.title("📁 Dashboard Marketing")
        st.write("Connectez-vous avec votre compte elem.global pour continuer.")
        if st.button("Se connecter avec Microsoft", type="primary"):
            st.login("microsoft")
        st.stop()

    try:
        allowed = st.secrets.get("ALLOWED_EMAIL_DOMAIN", "elem.global")
    except Exception:
        allowed = "elem.global"
    email = (getattr(st.user, "email", "") or "").lower()
    if not email.endswith("@" + allowed):
        st.error(f"Accès réservé aux comptes @{allowed}.")
        if st.button("Se déconnecter"):
            st.logout()
        st.stop()

    import approvals
    record_id = approvals.target_record_id(st.query_params)
    if record_id:
        import approval_page
        approval_page.render(record_id)
    else:
        import dashboard
        dashboard.render()


main()
