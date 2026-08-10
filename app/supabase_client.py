"""
supabase_client.py
Thin wrapper around the Supabase Python client, used ONLY for resume
metadata (who's in the system, file type, upload time). Embeddings and
similarity search do NOT go through Supabase - see vector_store.py.

Uses the service_role key on purpose: this app never runs in a browser,
so it's safe to use the elevated key here. Never expose this key client-side.
"""
import os
from datetime import datetime, timezone
from typing import Optional

from supabase import create_client, Client

_client: Optional[Client] = None


def get_client() -> Optional[Client]:
    """
    Returns a cached Supabase client, or None if SUPABASE_URL /
    SUPABASE_SERVICE_ROLE_KEY aren't configured. Metadata sync is optional -
    the app should keep working (Chroma + local files) even without Supabase.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key or "your-project-ref" in url:
        return None

    _client = create_client(url, key)
    return _client


def upsert_resume_metadata(
    resume_id: str,
    candidate_name: str,
    file_name: str,
    file_type: str,
    role_title: str = "",
) -> bool:
    """Insert or update a resume's metadata row. Returns True on success."""
    client = get_client()
    if client is None:
        return False

    client.table("resumes").upsert(
        {
            "resume_id": resume_id,
            "candidate_name": candidate_name,
            "role_title": role_title,
            "file_name": file_name,
            "file_type": file_type,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()
    return True


def list_resume_metadata() -> list[dict]:
    """Return all resume metadata rows, or [] if Supabase isn't configured."""
    client = get_client()
    if client is None:
        return []
    result = client.table("resumes").select("*").order("uploaded_at", desc=True).execute()
    return result.data or []
