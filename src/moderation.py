"""Moderation queue for Phase 3: manual approval of posts before publishing."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from logger import get_logger

logger = get_logger("news_bot.moderation")


class ModerationQueue:
    """Manages post approval workflow before publishing."""

    # Post statuses in moderation workflow
    STATUS_DRAFT = "draft"                     # Just created
    STATUS_PENDING_APPROVAL = "pending_approval"  # Waiting for owner review
    STATUS_APPROVED = "approved"               # Approved, ready to publish
    STATUS_SCHEDULED = "scheduled"             # Approved and scheduled for later
    STATUS_PUBLISHED = "published"             # Published to channel
    STATUS_REJECTED = "rejected"               # Rejected by owner
    STATUS_FAILED = "failed"                   # Failed to publish

    def __init__(self, db_path: str = "data/news_bot.db"):
        """Initialize moderation queue."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_columns()

    def _ensure_columns(self):
        """Ensure moderation columns exist in post_queue table."""
        with sqlite3.connect(self.db_path) as conn:
            # Check existing columns
            cursor = conn.execute("PRAGMA table_info(post_queue)")
            existing_cols = {row[1] for row in cursor.fetchall()}

            # Add new columns if they don't exist
            new_columns = [
                ("approved_at", "DATETIME"),
                ("approved_by", "TEXT"),
                ("rejection_reason", "TEXT"),
                ("rubric", "TEXT"),
                ("hashtags", "TEXT"),
                ("day_of_week", "TEXT"),
            ]

            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    try:
                        conn.execute(
                            f"ALTER TABLE post_queue ADD COLUMN {col_name} {col_type}"
                        )
                        logger.info(f"Added column {col_name} to post_queue")
                    except sqlite3.OperationalError:
                        pass

            conn.commit()

    def send_for_approval(self, post_id: int) -> bool:
        """
        Mark post as pending approval.

        Args:
            post_id: ID of the post to send for approval

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (self.STATUS_PENDING_APPROVAL, post_id,
                 self.STATUS_DRAFT, "pending"),
            )
            conn.commit()
            logger.info(f"Post {post_id} sent for approval")
            return True

    def approve_post(self, post_id: int, approved_by: str = "owner") -> bool:
        """
        Approve a post for immediate publishing.

        Args:
            post_id: ID of the post to approve
            approved_by: Who approved (user ID or name)

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = ?, approved_at = ?, approved_by = ?
                WHERE id = ? AND status = ?
                """,
                (
                    self.STATUS_APPROVED,
                    datetime.now().isoformat(),
                    approved_by,
                    post_id,
                    self.STATUS_PENDING_APPROVAL,
                ),
            )
            conn.commit()
            logger.info(f"Post {post_id} approved by {approved_by}")
            return True

    def schedule_post(
        self, post_id: int, scheduled_time: datetime, approved_by: str = "owner"
    ) -> bool:
        """
        Approve and schedule a post for later publishing.

        Args:
            post_id: ID of the post
            scheduled_time: When to publish
            approved_by: Who approved

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = ?, scheduled_at = ?, approved_at = ?, approved_by = ?
                WHERE id = ? AND status = ?
                """,
                (
                    self.STATUS_SCHEDULED,
                    scheduled_time.isoformat(),
                    datetime.now().isoformat(),
                    approved_by,
                    post_id,
                    self.STATUS_PENDING_APPROVAL,
                ),
            )
            conn.commit()
            logger.info(f"Post {post_id} scheduled for {scheduled_time}")
            return True

    def reject_post(self, post_id: int, reason: str = "") -> bool:
        """
        Reject a post (won't be published).

        Args:
            post_id: ID of the post
            reason: Rejection reason

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = ?, rejection_reason = ?
                WHERE id = ? AND status = ?
                """,
                (self.STATUS_REJECTED, reason, post_id, self.STATUS_PENDING_APPROVAL),
            )
            conn.commit()
            logger.info(f"Post {post_id} rejected: {reason}")
            return True

    def update_post_text(self, post_id: int, new_text: str) -> bool:
        """
        Edit post text before approval.

        Args:
            post_id: ID of the post
            new_text: New post text

        Returns:
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET post_text = ?
                WHERE id = ? AND status = ?
                """,
                (new_text, post_id, self.STATUS_PENDING_APPROVAL),
            )
            conn.commit()
            logger.info(f"Post {post_id} text updated")
            return True

    def get_pending_posts(self, limit: int = 20) -> List[Dict]:
        """
        Get all posts pending approval.

        Args:
            limit: Maximum number of posts to return

        Returns:
            List of post dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM post_queue
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (self.STATUS_PENDING_APPROVAL, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_approved_posts(self) -> List[Dict]:
        """
        Get posts approved but not yet published.

        Returns:
            List of post dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM post_queue
                WHERE status = ?
                ORDER BY approved_at ASC
                """,
                (self.STATUS_APPROVED,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_scheduled_posts(self) -> List[Dict]:
        """
        Get scheduled posts ready to publish.

        Returns:
            List of post dicts whose scheduled_at has passed
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM post_queue
                WHERE status = ? AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                """,
                (self.STATUS_SCHEDULED, now),
            )
            return [dict(row) for row in cursor.fetchall()]

    def mark_published(self, post_id: int) -> bool:
        """Mark post as published."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = ?, published_at = ?
                WHERE id = ?
                """,
                (self.STATUS_PUBLISHED, datetime.now().isoformat(), post_id),
            )
            conn.commit()
            logger.info(f"Post {post_id} marked as published")
            return True

    def mark_failed(self, post_id: int, error: str) -> bool:
        """Mark post as failed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE post_queue
                SET status = ?, error_message = ?
                WHERE id = ?
                """,
                (self.STATUS_FAILED, error, post_id),
            )
            conn.commit()
            logger.error(f"Post {post_id} failed: {error}")
            return True

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

    def auto_reject_old_posts(self, hours: int = 48) -> int:
        """
        Auto-reject posts pending approval for too long.

        Args:
            hours: Reject posts older than this many hours

        Returns:
            Number of rejected posts
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE post_queue
                SET status = ?, rejection_reason = ?
                WHERE status = ? AND created_at < ?
                """,
                (
                    self.STATUS_REJECTED,
                    f"Auto-rejected: not approved within {hours} hours",
                    self.STATUS_PENDING_APPROVAL,
                    cutoff,
                ),
            )
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info(f"Auto-rejected {count} old posts")
            return count

    def get_moderation_stats(self) -> Dict:
        """Get moderation queue statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Pending count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM post_queue WHERE status = ?",
                (self.STATUS_PENDING_APPROVAL,),
            )
            pending = cursor.fetchone()[0]

            # Approved today
            today = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM post_queue
                WHERE status IN (?, ?, ?) AND approved_at >= ?
                """,
                (self.STATUS_APPROVED, self.STATUS_SCHEDULED,
                 self.STATUS_PUBLISHED, today),
            )
            approved_today = cursor.fetchone()[0]

            # Rejected today
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM post_queue
                WHERE status = ? AND created_at >= ?
                """,
                (self.STATUS_REJECTED, today),
            )
            rejected_today = cursor.fetchone()[0]

            # Published today
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM post_queue
                WHERE status = ? AND published_at >= ?
                """,
                (self.STATUS_PUBLISHED, today),
            )
            published_today = cursor.fetchone()[0]

            return {
                "pending_approval": pending,
                "approved_today": approved_today,
                "rejected_today": rejected_today,
                "published_today": published_today,
            }


# Singleton instance
_moderation_queue: Optional[ModerationQueue] = None


def get_moderation_queue() -> ModerationQueue:
    """Get or create moderation queue singleton."""
    global _moderation_queue
    if _moderation_queue is None:
        _moderation_queue = ModerationQueue()
    return _moderation_queue


if __name__ == "__main__":
    # Test the moderation queue
    mq = ModerationQueue()
    print("Moderation queue initialized")
    print(f"Stats: {mq.get_moderation_stats()}")
    print(f"Pending posts: {len(mq.get_pending_posts())}")
