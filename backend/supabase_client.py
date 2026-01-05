import os
import json
from supabase import create_client, Client

# Initialize Supabase Client
url: str = os.environ.get("FOOD_CACHE_SUPABASE_URL", "")
key: str = os.environ.get("FOOD_CACHE_SUPABASE_SERVICE_ROLE_KEY", "")

supabase: Client = None

if url and key:
    try:
        supabase = create_client(url, key)
    except Exception as e:
        print(f"Failed to initialize Supabase client: {e}")

def get_cached_results(query: str):
    """
    Retrieve cached search results from Supabase.
    """
    if not supabase:
        return None

    try:
        response = supabase.table("search_cache").select("results").eq("query", query).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["results"]
    except Exception as e:
        print(f"Error fetching from Supabase cache: {e}")
    
    return None

def cache_results(query: str, results: dict):
    """
    Save search results to Supabase cache.
    """
    if not supabase:
        return

    try:
        data = {
            "query": query,
            "results": results,
            # created_at is automatic if default is set, otherwise we might need it
        }
        # Upsert allows overwriting if query already exists
        supabase.table("search_cache").upsert(data).execute()
    except Exception as e:
        print(f"Error saving to Supabase cache: {e}")
