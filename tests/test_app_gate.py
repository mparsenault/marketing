from streamlit.testing.v1 import AppTest


def test_shows_login_when_logged_out():
    at = AppTest.from_file("app.py")
    at.run()
    assert not at.exception
    # Écran de connexion visible tant que non authentifié
    assert any("Connectez-vous" in md.value for md in at.markdown), \
        "Le message de connexion devrait s'afficher"
    assert any(b.label == "Se connecter avec Microsoft" for b in at.button)
