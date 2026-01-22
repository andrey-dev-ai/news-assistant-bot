"""Database for tracking sent articles."""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from logger import get_logger

logger = get_logger("news_bot.db")


class Database:
    """SQLite database for tracking sent articles."""

    def __init__(self, db_path: str = "data/news_bot.db"):
        """Initialize database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Check if table exists (for migration)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sent_articles'"
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Migration: add new columns FIRST before creating indexes
                self._migrate_add_columns(conn)
            else:
                # Create new table with all columns
                conn.execute("""
                    CREATE TABLE sent_articles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        article_link TEXT UNIQUE NOT NULL,
                        title TEXT,
                        title_normalized TEXT,
                        url_normalized TEXT,
                        relevance_score INTEGER DEFAULT 0,
                        category TEXT,
                        status TEXT DEFAULT 'published',
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            # Create indexes (now safe - columns exist)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_article_link
                ON sent_articles(article_link)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_url_normalized
                ON sent_articles(url_normalized)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_title_normalized
                ON sent_articles(title_normalized)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sent_at
                ON sent_articles(sent_at)
            """)

            conn.commit()

    def _migrate_add_columns(self, conn):
        """Add new columns to existing tables if they don't exist."""
        # Get existing columns
        cursor = conn.execute("PRAGMA table_info(sent_articles)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        new_columns = [
            ("title_normalized", "TEXT"),
            ("url_normalized", "TEXT"),
            ("relevance_score", "INTEGER DEFAULT 0"),
            ("category", "TEXT"),
            ("status", "TEXT DEFAULT 'published'"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                try:
                    conn.execute(
                        f"ALTER TABLE sent_articles ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"Added column {col_name} to sent_articles")
                except sqlite3.OperationalError:
                    pass  # Column already exists

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL for deduplication."""
        if not url:
            return ""
        url = url.lower().strip()
        url = re.sub(r"^https?://", "", url)
        url = re.sub(r"^www\.", "", url)
        url = url.rstrip("/")
        url = re.sub(r"\?utm_[^&]+(&utm_[^&]+)*", "", url)
        return url

    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize title for deduplication."""
        if not title:
            return ""
        title = title.lower()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title).strip()
        return title

    def is_article_sent(self, link: str) -> bool:
        """Check if article was already sent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM sent_articles WHERE article_link = ?",
                (link,)
            )
            return cursor.fetchone() is not None

    def mark_article_sent(
        self,
        link: str,
        title: str = "",
        relevance_score: int = 0,
        category: str = "",
        status: str = "published",
    ):
        """Mark article as sent with normalized fields."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO sent_articles
                    (article_link, title, title_normalized, url_normalized,
                     relevance_score, category, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        link,
                        title,
                        self.normalize_title(title),
                        self.normalize_url(link),
                        relevance_score,
                        category,
                        status,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            # Article already exists
            pass

    def filter_unsent_articles(self, articles: List[dict]) -> List[dict]:
        """Filter out already sent articles."""
        unsent = []
        for article in articles:
            if not self.is_article_sent(article['link']):
                unsent.append(article)
        return unsent

    def cleanup_old_records(self, days: int = 30):
        """Remove records older than specified days."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM sent_articles
                WHERE sent_at < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )
            conn.commit()

    def get_stats(self) -> dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*), MAX(sent_at) FROM sent_articles"
            )
            count, last_sent = cursor.fetchone()

            # Queue stats
            cursor = conn.execute(
                """SELECT COUNT(*) FROM post_queue
                WHERE status = 'pending' AND scheduled_at > datetime('now')"""
            )
            queue_count = cursor.fetchone()[0] or 0

            # Today's stats
            cursor = conn.execute(
                """SELECT COUNT(*) FROM sent_articles
                WHERE date(sent_at) = date('now')"""
            )
            today_count = cursor.fetchone()[0] or 0

            # Category breakdown
            cursor = conn.execute(
                """SELECT category, COUNT(*) FROM sent_articles
                WHERE sent_at > datetime('now', '-7 days')
                GROUP BY category"""
            )
            categories = {row[0] or "unknown": row[1] for row in cursor.fetchall()}

            return {
                "total_articles": count or 0,
                "last_sent": last_sent,
                "queue_size": queue_count,
                "today_published": today_count,
                "categories_7d": categories,
            }

    def get_recent_titles(self, days: int = 7, limit: int = 1000) -> List[Tuple[str, str]]:
        """Get recent titles for deduplicator initialization."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT title, article_link FROM sent_articles
                WHERE sent_at > datetime('now', '-' || ? || ' days')
                ORDER BY sent_at DESC
                LIMIT ?""",
                (days, limit),
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]

    def add_to_queue(
        self,
        article_link: str,
        title: str,
        post_text: str,
        post_format: str,
        image_prompt: str = "",
        scheduled_at: Optional[str] = None,
    ) -> int:
        """Add post to queue."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO post_queue
                (article_link, title, post_text, post_format, image_prompt, scheduled_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (article_link, title, post_text, post_format, image_prompt, scheduled_at),
            )
            conn.commit()
            return cursor.lastrowid

    def get_pending_posts(self, limit: int = 10) -> List[Dict]:
        """Get pending posts from queue."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT * FROM post_queue
                WHERE status = 'pending'
                AND (scheduled_at IS NULL OR scheduled_at <= datetime('now'))
                ORDER BY scheduled_at ASC, created_at ASC
                LIMIT ?""",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_queue_status(self, queue_id: int, status: str):
        """Update post queue status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE post_queue SET status = ? WHERE id = ?",
                (status, queue_id),
            )
            conn.commit()

    def get_daily_summary(self, days: int = 7) -> List[Dict]:
        """Get daily summary for monitoring."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT
                    date(sent_at) as day,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    ROUND(AVG(relevance_score), 1) as avg_relevance
                FROM sent_articles
                WHERE sent_at > datetime('now', '-' || ? || ' days')
                GROUP BY date(sent_at)
                ORDER BY day DESC""",
                (days,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_queue_health(self) -> Dict:
        """Get queue health status for monitoring."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT
                    COUNT(*) as posts_in_buffer,
                    MIN(scheduled_at) as next_post,
                    MAX(scheduled_at) as last_scheduled
                FROM post_queue
                WHERE status = 'pending' AND scheduled_at > datetime('now')"""
            )
            row = cursor.fetchone()
            count = row[0] or 0

            if count < 5:
                health_status = "critical"
            elif count < 10:
                health_status = "warning"
            else:
                health_status = "ok"

            return {
                "posts_in_buffer": count,
                "next_post": row[1],
                "last_scheduled": row[2],
                "health_status": health_status,
            }


if __name__ == "__main__":
    # Test database
    db = Database()

    # Test data
    test_article = {
        'link': 'https://example.com/test',
        'title': 'Test Article'
    }

    print("Testing database...")
    print(f"Stats: {db.get_stats()}")

    # Test marking as sent
    db.mark_article_sent(test_article['link'], test_article['title'])
    print(f"Is article sent: {db.is_article_sent(test_article['link'])}")

    # Test filtering
    articles = [
        test_article,
        {'link': 'https://example.com/new', 'title': 'New Article'}
    ]
    unsent = db.filter_unsent_articles(articles)
    print(f"Unsent articles: {len(unsent)}")
