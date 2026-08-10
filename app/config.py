"""
config.py
Reads app configuration (API keys, etc.) from either Streamlit Community
Cloud's secrets manager (st.secrets) or a local .env file, so the same
codebase works unchanged in both places.

Precedence: st.secrets (Streamlit Cloud) > os.environ (.env / real env vars).
"""
import os

from dotenv import load_dotenv

load_dotenv()  # no-op if .env doesn't exist (e.g. on Streamlit Cloud)

try:
    import streamlit as st
    _HAS_STREAMLIT_SECRETS = True
except ImportError:
    _HAS_STREAMLIT_SECRETS = False


def get_setting(key: str, default: str | None = None) -> str | None:
    """Fetch a config value, preferring Streamlit Cloud secrets when present."""
    if _HAS_STREAMLIT_SECRETS:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            # st.secrets raises if no secrets.toml exists at all (e.g. local
            # run without Streamlit Cloud) - fall through to os.environ.
            pass
    return os.environ.get(key, default)


# Convenience constants used across the app
GROQ_API_KEY = get_setting("GROQ_API_KEY")
GROQ_MODEL = get_setting("GROQ_MODEL", "llama-3.3-70b-versatile")
SUPABASE_URL = get_setting("SUPABASE_URL")
SUPABASE_KEY = get_setting("SUPABASE_KEY")


def groq_is_configured() -> bool:
    return bool(GROQ_API_KEY)


def supabase_is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)
