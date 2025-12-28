from supabase import Client

# Global client - set during app startup
_supabase_client: Client | None = None


def set_supabase_client(client: Client) -> None:
    """Set the global Supabase client (called from app lifespan)."""
    global _supabase_client
    _supabase_client = client


def get_supabase() -> Client | None:
    """Get the shared Supabase client."""
    return _supabase_client