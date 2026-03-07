import os
import psycopg

def get_db_connection():
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise ValueError("SUPABASE_DB_URL not set")
    if "sslmode" not in db_url:
        db_url += "?sslmode=require"
    return psycopg.connect(db_url, prepare_threshold=None)