"""Database for tracking sent articles."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List


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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_link TEXT UNIQUE NOT NULL,
                    title TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_article_link
                ON sent_articles(article_link)
            """)
            conn.commit()

    def is_article_sent(self, link: str) -> bool:
        """Check if article was already sent."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM sent_articles WHERE article_link = ?",
                (link,)
            )
            return cursor.fetchone() is not None

    def mark_article_sent(self, link: str, title: str = ""):
        """Mark article as sent."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO sent_articles (article_link, title) VALUES (?, ?)",
                    (link, title)
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
            return {
                'total_articles': count or 0,
                'last_sent': last_sent
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
