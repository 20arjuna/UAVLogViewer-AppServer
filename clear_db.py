#!/usr/bin/env python3
"""
Utility script to clear all tables from the DuckDB database.
"""
import duckdb
from pathlib import Path

# Path to the database
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tmp" / "uav_logs.duckdb"

def clear_database():
    """Drop all tables from the database."""
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return
    
    conn = duckdb.connect(str(DB_PATH))
    
    # Get all table names
    tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()
    
    if not tables:
        print("✅ Database is already empty (no tables found)")
        conn.close()
        return
    
    print(f"Found {len(tables)} table(s) to drop:")
    for table in tables:
        table_name = table[0]
        print(f"  - {table_name}")
    
    # Drop all tables
    for table in tables:
        table_name = table[0]
        conn.execute(f'DROP TABLE "{table_name}"')
        print(f"✅ Dropped {table_name}")
    
    conn.close()
    print(f"\n🎉 All tables cleared from {DB_PATH}")

if __name__ == "__main__":
    clear_database()

