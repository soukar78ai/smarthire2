"""
config.py
Settings for the equity agents. Reuses the SmartHire2 resolution order:
st.secrets (Streamlit Cloud) > os.environ (.env / real env vars).
"""
from pathlib import Path

from app.config import get_setting

GROQ_API_KEY = get_setting("GROQ_API_KEY")
GROQ_MODEL = get_setting("GROQ_MODEL", "llama-3.3-70b-versatile")

# How far back the news agents look, and how many headlines they read
NEWS_LOOKBACK_DAYS = int(get_setting("EQUITY_NEWS_LOOKBACK_DAYS", "7"))
MAX_HEADLINES = int(get_setting("EQUITY_MAX_HEADLINES", "15"))

PACKAGE_DIR = Path(__file__).parent
WATCHLIST_PATH = Path(get_setting("EQUITY_WATCHLIST", str(PACKAGE_DIR / "watchlist.txt")))
REPORTS_DIR = Path(get_setting("EQUITY_REPORTS_DIR", str(PACKAGE_DIR.parent / "reports")))


def groq_is_configured() -> bool:
    return bool(GROQ_API_KEY) and GROQ_API_KEY != "your_groq_api_key_here"
