# Dashboard Marketing — version Streamlit (Projets)

App Streamlit qui reproduit l'onglet Projets, lisant/écrivant dans Airtable,
protégée par login Microsoft Entra ID.

## Installation

```bash
cd streamlit_app
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copier `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et remplir :

- **Airtable** : `AIRTABLE_PAT`, `AIRTABLE_BASE_ID` (`appScszc5IPkA58HX`), `AIRTABLE_TABLE_NAME` (`Projets`).
- **Entra (OIDC)** : `client_id`, `client_secret`, `server_metadata_url`, plus `redirect_uri` et `cookie_secret`.

### Créer l'app registration Entra (Azure)

1. Azure Portal → Microsoft Entra ID → App registrations → New registration.
2. Redirect URI (type Web) = `http://localhost:8501/oauth2callback` (adapter à l'URL de déploiement).
3. Récupérer l'**Application (client) ID** → `client_id`.
4. Certificates & secrets → New client secret → copier la valeur → `client_secret`.
5. `server_metadata_url` = `https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration`.
6. Générer un `cookie_secret` aléatoire long (ex. `python -c "import secrets; print(secrets.token_hex(32))"`).

## Lancer

```bash
streamlit run app.py
```

## Tests

```bash
pytest -v
```
