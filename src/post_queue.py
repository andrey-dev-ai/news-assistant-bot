"""SQLite queue for scheduled posts."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from logger import get_logger

logger = get_logger("news_bot.post_queue")


class PostQueue:
    """SQLite-based queue for scheduled posts."""

    def __init__(self, db_path: str = "data/news_bot.db"):
        """Initialize post queue."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        """Create post_queue table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS post_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_url TEXT,
                    article_title TEXT,
                    post_text TEXT NOT NULL,
                    image_url TEXT,
                    image_prompt TEXT,
                    format TEXT DEFAULT 'ai_tool',
                    scheduled_at DATETIME,
                    published_at DATETIME,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_post_queue_status
                ON post_queue(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_post_queue_scheduled
                ON post_queue(scheduled_at)
            """)
            conn.commit()
            logger.info("Post queue table initialized")

    def add_post(
        self,
        post_text: str,
        article_url: str = "",
        article_title: str = "",
        image_url: str = None,
        image_prompt: str = None,
        format_type: str = "ai_tool",
        scheduled_at: datetime = None,
    ) -> int:
        """
        Add a post to the queue.

        Returns:
            ID of the inserted post
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO post_queue
                (article_url, article_title, post_text, image_url, image_prompt,
                 format, scheduled_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    article_url,
                    article_title,
                    post_text,
                    image_url,
                    image_prompt,
                    format_type,
                    scheduled_at.isoformat() if scheduled_at else None,
                ),
            )
            conn.commit()
            post_id = cursor.lastrowid
            logger.info(f"Added post to queue: id={post_id}, format={format_type}")
            return post_id

    def get_next_pending(self) -> Optional[Dict]:
        """
        Get next pending post that should be published.

        Returns:
            Post dict or None
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM post_queue
                WHERE status = 'pending'
                AND (scheduled_at IS NULL OR scheduled_at <= ?)
                ORDER BY scheduled_at ASC, id ASC
                LIMIT 1
                """,
                (now,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_pending_count(self) -> int:
        """Get count of pending posts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM post_queue WHERE status = 'pending'"
            )
            return cursor.fetchone()[0]

    def get_posts_for_today(self) -> List[Dict]:
        """Get all posts scheduled for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        today_end = today_start + timedelta(days=1)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM post_queue
                WHERE scheduled_at >= ? AND scheduled_at < ?
                ORDER BY scheduled_at ASC
                """,
                (today_start.isoformat(), today_end.isoformat()),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_pending(self, limit: int = 10) -> List[Dict]:
        """Get all pending posts regardless of date."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM post_queue
                WHERE status = 'pending'
                ORDER BY scheduled_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_post_by_id(self, post_id: int) -> Optional[Dict]:
        """Get a single post by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM post_queue WHERE id = ?",
                (post_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def mark_published(self, post_id: int) -> bool:
        """Mark post as published."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = 'published', published_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), post_id),
            )
            conn.commit()
            logger.info(f"Post {post_id} marked as published")
            return True

    def mark_failed(self, post_id: int, error_message: str) -> bool:
        """Mark post as failed with error message."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = 'failed', error_message = ?
                WHERE id = ?
                """,
                (error_message, post_id),
            )
            conn.commit()
            logger.error(f"Post {post_id} marked as failed: {error_message}")
            return True

    def update_image_url(self, post_id: int, image_url: str) -> bool:
        """Update image URL for a post."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE post_queue SET image_url = ? WHERE id = ?",
                (image_url, post_id),
            )
            conn.commit()
            logger.info(f"Post {post_id} image URL updated")
            return True

    def schedule_posts_for_day(
        self,
        posts: List[Dict],
        times: List[str] = None,
        date: datetime = None,
    ) -> List[int]:
        """
        Schedule multiple posts for specific times.

        Args:
            posts: List of post dicts with keys: text, article_url, article_title,
                   image_prompt, format
            times: List of times in "HH:MM" format (default: 09:00, 12:00, 15:00, 18:00, 21:00)
            date: Date to schedule for (default: today)

        Returns:
            List of inserted post IDs
        """
        if times is None:
            times = ["09:00", "12:00", "15:00", "18:00", "21:00"]

        if date is None:
            date = datetime.now()

        # Use only as many times as we have posts
        times = times[: len(posts)]

        post_ids = []
        for i, (post, time_str) in enumerate(zip(posts, times)):
            hour, minute = map(int, time_str.split(":"))
            scheduled_at = date.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time already passed today, schedule for tomorrow
            if scheduled_at < datetime.now():
                scheduled_at += timedelta(days=1)

            post_id = self.add_post(
                post_text=post.get("text", ""),
                article_url=post.get("article_url", ""),
                article_title=post.get("article_title", ""),
                image_url=post.get("image_url"),  # From article OG/RSS
                image_prompt=post.get("image_prompt"),
                format_type=post.get("format", "ai_tool"),
                scheduled_at=scheduled_at,
            )
            post_ids.append(post_id)
            logger.info(f"Scheduled post {post_id} for {scheduled_at}")

        return post_ids

    def get_stats(self) -> Dict:
        """Get queue statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    status,
                    COUNT(*) as count
                FROM post_queue
                GROUP BY status
            """)
            stats = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute(
                "SELECT COUNT(*) FROM post_queue WHERE published_at >= date('now')"
            )
            stats["published_today"] = cursor.fetchone()[0]

            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM post_queue
                WHERE status = 'pending' AND scheduled_at >= datetime('now')
                """
            )
            stats["scheduled_future"] = cursor.fetchone()[0]

            return stats

    def cleanup_old_posts(self, days: int = 30) -> int:
        """
        Remove posts older than specified days.

        Returns:
            Number of deleted posts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM post_queue
                WHERE created_at < datetime('now', '-' || ? || ' days')
                AND status IN ('published', 'failed')
                """,
                (days,),
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old posts")
            return deleted

    def retry_failed_posts(self) -> int:
        """
        Reset failed posts to pending for retry.

        Returns:
            Number of posts reset
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE post_queue
                SET status = 'pending', error_message = NULL
                WHERE status = 'failed'
                """
            )
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info(f"Reset {count} failed posts to pending")
            return count


if __name__ == "__main__":
    # Test the queue
    queue = PostQueue()

    print("Testing post queue...")
    print(f"Stats: {queue.get_stats()}")

    # Add test post
    post_id = queue.add_post(
        post_text="🤖 AI-находка дня: Test Tool\n\nЭто тестовый пост!",
        article_url="https://example.com/test",
        article_title="Test Article",
        image_prompt="Flat design, pastel colors, AI assistant icon",
        format_type="ai_tool",
    )
    print(f"Added post with ID: {post_id}")

    # Get pending
    pending = queue.get_next_pending()
    print(f"Next pending: {pending}")

    # Stats
    print(f"Stats after add: {queue.get_stats()}")
