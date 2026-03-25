"""
Database migrations for Fallco Aste Bot.
"""
import logging
import sqlite3
from pathlib import Path


logger = logging.getLogger(__name__)


def create_tables(db_path: str = "data/fallco_bot.db") -> None:
    """
    Create all database tables.
    
    Args:
        db_path: Path to SQLite database file
    """
    # Ensure directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Auctions seen table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auctions_seen (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT,
            current_price REAL,
            base_price REAL,
            end_datetime TEXT,
            start_datetime TEXT,
            location TEXT,
            tribunal TEXT,
            procedure_number TEXT,
            description TEXT,
            images TEXT,
            raw_data TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            auction_hash TEXT NOT NULL
        )
    """)
    
    # Create index on end_datetime for filtering
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_auctions_end_datetime 
        ON auctions_seen(end_datetime)
    """)
    
    # Create index on last_seen for cleanup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_auctions_last_seen 
        ON auctions_seen(last_seen)
    """)
    
    # Alerts sent table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            resale_value REAL NOT NULL,
            max_bid REAL NOT NULL,
            roi REAL NOT NULL,
            margin REAL NOT NULL,
            detected_at TEXT NOT NULL,
            sent_at TEXT NOT NULL
        )
    """)
    
    # Create index on url for dedup checks
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_url 
        ON alerts_sent(url)
    """)
    
    # Create index on sent_at for cleanup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_alerts_sent_at 
        ON alerts_sent(sent_at)
    """)
    
    # Gold price cache table (for caching gold spot prices)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_price_cache (
            id INTEGER PRIMARY KEY,
            price REAL NOT NULL,
            fetched_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database tables created at {db_path}")


def drop_tables(db_path: str = "data/fallco_bot.db") -> None:
    """
    Drop all database tables (for testing/reset).
    
    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS auctions_seen")
    cursor.execute("DROP TABLE IF EXISTS alerts_sent")
    cursor.execute("DROP TABLE IF EXISTS gold_price_cache")
    
    conn.commit()
    conn.close()
    
    logger.warning(f"Dropped all tables in {db_path}")


def get_schema(db_path: str = "data/fallco_bot.db") -> str:
    """
    Get current database schema.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        Schema as string
    """
    if not Path(db_path).exists():
        return "Database does not exist"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    schema_lines = []
    for table in tables:
        schema_lines.append(f"\n--- Table: {table} ---")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            schema_lines.append(f"  {col[1]} {col[2]}")
    
    conn.close()
    
    return '\n'.join(schema_lines)


def migrate(db_path: str = "data/fallco_bot.db") -> None:
    """
    Run migrations (creates tables if they don't exist).
    
    Args:
        db_path: Path to SQLite database file
    """
    create_tables(db_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "data/fallco_bot.db"
    
    if len(sys.argv) > 2 and sys.argv[2] == "--drop":
        drop_tables(db_path)
        print(f"Dropped tables in {db_path}")
    
    migrate(db_path)
    print(f"Migration complete for {db_path}")
    print(get_schema(db_path))