"""Supabase client singleton.

Usage:
    from db.client import supabase
    result = supabase.table("companies").select("*").execute()
"""

from supabase import create_client, Client
import config

_client: Client | None = None


def get_client() -> Client:
    """Return a shared Supabase client (creates it on first call)."""
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _client


# Convenience shortcut — import this directly
supabase = get_client()
