"""Pytest configuration for Streamlit AppTest suite.

Fixture: Ensures streamlit_app/.streamlit/secrets.toml exists with minimal auth config.

Why: Streamlit's auth singleton reads a real secrets file on disk at startup.
AppTest.secrets does not substitute for it, so tests fail without the file.
This fixture auto-provisions it if absent, then cleans up at session end.
"""

import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_secrets_toml():
    """
    Auto-provision secrets.toml stub for tests if not present.

    - Computes path relative to conftest location
    - If absent: creates .streamlit/ dir if needed, writes minimal stub, then deletes at session end
    - If present: leaves untouched, does not delete
    """
    secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    created_by_fixture = False
    created_dir = False

    # If file doesn't exist, create it
    if not secrets_path.exists():
        created_by_fixture = True

        # Create .streamlit dir if it doesn't exist
        secrets_path.parent.mkdir(parents=True, exist_ok=True)
        # Track if we created the dir (for cleanup)
        created_dir = True

        # Write minimal stub
        stub_content = """# Auto-provisioned by pytest fixture for AppTest suite.
# Dummy values; replace with real secrets for local development.

AIRTABLE_PAT = "patPlaceholder"
AIRTABLE_BASE_ID = "appPlaceholder"
AIRTABLE_TABLE_NAME = "Projets"

[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "placeholder_cookie_secret_for_tests"

[auth.microsoft]
client_id = "placeholder-client-id"
client_secret = "placeholder_client_secret"
server_metadata_url = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
"""
        secrets_path.write_text(stub_content)

    yield

    # Cleanup: delete stub file if fixture created it
    if created_by_fixture and secrets_path.exists():
        secrets_path.unlink()
        # Remove .streamlit dir only if fixture created it AND it's now empty
        if created_dir and not any(secrets_path.parent.iterdir()):
            secrets_path.parent.rmdir()
