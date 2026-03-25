"""
Database storage for Fallco Aste Bot.
"""
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from ..models import Auction, Opportunity, AuctionCategory, AuctionCache


logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database for storing auctions and alerts.
    """
    
    def __init__(self, db_path: str = "data/fallco_bot.db"):
        """
        Initialize database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_dir()
        self._conn: Optional[sqlite3.Connection] = None
    
    def _ensure_db_dir(self) -> None:
        """Ensure database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ========== AUCTION TRACKING ==========
    
    def save_auction(self, auction: Auction) -> None:
        """
        Save or update an auction in the database.
        
        Args:
            auction: Auction to save
        """
        conn = self.conn
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO auctions_seen
            (url, title, category, current_price, base_price, end_datetime,
             start_datetime, location, tribunal, procedure_number,
             description, images, raw_data, first_seen, last_seen, auction_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            auction.url,
            auction.title,
            auction.category.value if auction.category else None,
            auction.current_price,
            auction.base_price,
            auction.end_datetime.isoformat() if auction.end_datetime else None,
            auction.start_datetime.isoformat() if auction.start_datetime else None,
            auction.location,
            auction.tribunal,
            auction.procedure_number,
            auction.description,
            ','.join(auction.images),
            str(auction.raw_data),
            auction.first_seen.isoformat(),
            auction.last_seen.isoformat(),
            auction.auction_hash,
        ))
        
        conn.commit()
    
    def auction_exists(self, url: str) -> bool:
        """Check if auction exists in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM auctions_seen WHERE url = ?", (url,))
        return cursor.fetchone() is not None
    
    def get_auction(self, url: str) -> Optional[Auction]:
        """Get auction from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM auctions_seen WHERE url = ?", (url,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_auction(row)
        return None
    
    def get_recent_auctions(self, hours: int = 24) -> List[Auction]:
        """Get auctions seen in the last N hours."""
        cursor = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute(
            "SELECT * FROM auctions_seen WHERE last_seen > ? ORDER BY last_seen DESC",
            (cutoff,)
        )
        
        return [self._row_to_auction(row) for row in cursor.fetchall()]
    
    def _row_to_auction(self, row: sqlite3.Row) -> Auction:
        """Convert database row to Auction object."""
        return Auction(
            url=row['url'],
            title=row['title'],
            category=AuctionCategory(row['category']) if row['category'] else None,
            current_price=row['current_price'],
            base_price=row['base_price'],
            end_datetime=datetime.fromisoformat(row['end_datetime']) if row['end_datetime'] else None,
            start_datetime=datetime.fromisoformat(row['start_datetime']) if row['start_datetime'] else None,
            location=row['location'],
            tribunal=row['tribunal'],
            procedure_number=row['procedure_number'],
            description=row['description'],
            images=row['images'].split(',') if row['images'] else [],
            raw_data=eval(row['raw_data']) if row['raw_data'] else {},
            first_seen=datetime.fromisoformat(row['first_seen']),
            last_seen=datetime.fromisoformat(row['last_seen']),
        )
    
    # ========== ALERTS ==========
    
    def save_alert(self, opportunity: Opportunity) -> None:
        """
        Save an alert that was sent.
        
        Args:
            opportunity: Opportunity that was alerted
        """
        conn = self.conn
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alerts_sent
            (url, title, category, resale_value, max_bid, roi, margin,
             detected_at, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            opportunity.auction.url,
            opportunity.auction.title,
            opportunity.category.value,
            opportunity.resale_value,
            opportunity.max_bid,
            opportunity.estimated_roi,
            opportunity.estimated_margin,
            opportunity.detected_at.isoformat(),
            datetime.now().isoformat(),
        ))
        
        conn.commit()
    
    def alert_exists(self, url: str, hours: int = 24) -> bool:
        """
        Check if alert was already sent for this auction within the window.
        
        Args:
            url: Auction URL
            hours: Time window in hours
            
        Returns:
            True if alert exists within window
        """
        cursor = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute(
            "SELECT 1 FROM alerts_sent WHERE url = ? AND sent_at > ?",
            (url, cutoff)
        )
        
        return cursor.fetchone() is not None
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alerts sent in the last N hours."""
        cursor = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute(
            "SELECT * FROM alerts_sent WHERE sent_at > ? ORDER BY sent_at DESC",
            (cutoff,)
        )
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== STATISTICS ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.conn.cursor()
        
        # Auction stats
        cursor.execute("SELECT COUNT(*) as total FROM auctions_seen")
        total_auctions = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM auctions_seen WHERE last_seen > ?",
                     ((datetime.now() - timedelta(hours=24)).isoformat(),))
        recent_auctions = cursor.fetchone()['total']
        
        # Alert stats
        cursor.execute("SELECT COUNT(*) as total FROM alerts_sent")
        total_alerts = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM alerts_sent WHERE sent_at > ?",
                     ((datetime.now() - timedelta(hours=24)).isoformat(),))
        recent_alerts = cursor.fetchone()['total']
        
        return {
            'total_auctions': total_auctions,
            'recent_auctions_24h': recent_auctions,
            'total_alerts': total_alerts,
            'recent_alerts_24h': recent_alerts,
        }
    
    # ========== MAINTENANCE ==========
    
    def cleanup_old_records(self, days: int = 30) -> int:
        """
        Clean up old records from database.
        
        Args:
            days: Keep records from last N days
            
        Returns:
            Number of records deleted
        """
        conn = self.conn
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Clean old auctions
        cursor.execute("DELETE FROM auctions_seen WHERE last_seen < ?", (cutoff,))
        auctions_deleted = cursor.row_count
        
        # Clean old alerts
        cursor.execute("DELETE FROM alerts_sent WHERE sent_at < ?", (cutoff,))
        alerts_deleted = cursor.row_count
        
        conn.commit()
        
        total_deleted = auctions_deleted + alerts_deleted
        logger.info(f"Cleaned up {total_deleted} old records")
        
        return total_deleted


def get_database(db_path: str = "data/fallco_bot.db") -> Database:
    """Get a Database instance."""
    return Database(db_path)