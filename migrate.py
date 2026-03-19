#!/usr/bin/env python3
"""
Migration script to add required columns to Supabase database
Run once before using the updated scraper
"""

from supabase import create_client

SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4"

def run_migration():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("Running database migration...")
    
    try:
        existing = client.table('products').select('updated_at, last_seen_run').limit(1).execute()
        print("Columns already exist!")
        return True
    except Exception as e:
        print(f"Need to add columns: {e}")
    
    migration_sql = """
    ALTER TABLE public.products ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
    ALTER TABLE public.products ADD COLUMN IF NOT EXISTS last_seen_run integer DEFAULT 0;
    """
    
    try:
        response = client.rpc('pg_catalog', {'sql': migration_sql}).execute()
        print("Migration completed successfully!")
        return True
    except Exception as e:
        print(f"RPC migration failed: {e}")
        print("\nPlease run this SQL manually in Supabase SQL Editor:")
        print("-" * 50)
        print(migration_sql)
        print("-" * 50)
        return False

if __name__ == "__main__":
    run_migration()
