"""
Unit tests for Database and PostQueue modules.

Tests cover:
- SQLite operations (CRUD)
- URL and title normalization
- Queue management
- Statistics and health checks
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestDatabaseNormalization:
    """Tests for Database normalization methods."""

    def test_normalize_url_static_method(self):
        """Database.normalize_url should work as static method."""
        from database import Database
        
        url = "https://www.example.com/article?utm_source=twitter"
        normalized = Database.normalize_url(url)
        
        assert normalized == "example.com/article"

    def test_normalize_title_static_method(self):
        """Database.normalize_title should work as static method."""
        from database import Database
        
        title = "The Best AI Tools! (2024)"
        normalized = Database.normalize_title(title)
        
        assert normalized == "the best ai tools 2024"

    def test_normalize_empty_inputs(self):
        """Normalization should handle empty inputs."""
        from database import Database
        
        assert Database.normalize_url("") == ""
        assert Database.normalize_url(None) == ""
        assert Database.normalize_title("") == ""
        assert Database.normalize_title(None) == ""


class TestDatabaseCRUD:
    """Tests for Database CRUD operations."""

    def test_mark_article_sent(self, test_database):
        """Should mark article as sent."""
        link = "https://example.com/test-article"
        title = "Test Article Title"
        
        test_database.mark_article_sent(
            link=link,
            title=title,
            relevance_score=85,
            category="tool"
        )
        
        assert test_database.is_article_sent(link)

    def test_is_article_sent_not_found(self, test_database):
        """Should return False for unsent articles."""
        assert not test_database.is_article_sent("https://example.com/unknown")

    def test_duplicate_article_handling(self, test_database):
        """Should handle duplicate article gracefully (IntegrityError)."""
        link = "https://example.com/duplicate"
        
        # First insert
        test_database.mark_article_sent(link, "Title 1")
        
        # Second insert should not raise
        test_database.mark_article_sent(link, "Title 2")
        
        # Should still exist
        assert test_database.is_article_sent(link)

    def test_filter_unsent_articles(self, test_database):
        """Should filter out sent articles."""
        # Mark one as sent
        test_database.mark_article_sent(
            "https://example.com/sent",
            "Sent Article"
        )
        
        articles = [
            {"link": "https://example.com/sent", "title": "Sent"},
            {"link": "https://example.com/new1", "title": "New 1"},
            {"link": "https://example.com/new2", "title": "New 2"},
        ]
        
        unsent = test_database.filter_unsent_articles(articles)
        
        assert len(unsent) == 2
        assert all(a["link"].endswith(("new1", "new2")) for a in unsent)


class TestDatabaseStats:
    """Tests for Database statistics methods."""

    def test_get_stats_empty(self, test_database):
        """Stats should work on empty database."""
        stats = test_database.get_stats()
        
        assert stats["total_articles"] == 0
        assert stats["today_published"] == 0

    def test_get_stats_with_data(self, populated_database):
        """Stats should reflect actual data."""
        stats = populated_database.get_stats()
        
        assert stats["total_articles"] == 5
        assert stats["today_published"] >= 0  # Depends on when test runs

    def test_get_recent_titles(self, populated_database):
        """Should return recent titles for deduplicator."""
        titles = populated_database.get_recent_titles(days=7, limit=10)
        
        assert len(titles) == 5
        assert all(isinstance(t, tuple) and len(t) == 2 for t in titles)


class TestDatabaseCleanup:
    """Tests for Database cleanup operations."""

    def test_cleanup_old_records(self, test_database, temp_db_path):
        """Should remove old records."""
        import sqlite3
        
        # Insert old record directly
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("""
                INSERT INTO sent_articles (article_link, title, sent_at)
                VALUES (?, ?, datetime('now', '-60 days'))
            """, ("https://old.com/article", "Old Article"))
            conn.commit()
        
        # Verify it exists
        assert test_database.is_article_sent("https://old.com/article")
        
        # Cleanup (30 days)
        test_database.cleanup_old_records(days=30)
        
        # Should be removed
        assert not test_database.is_article_sent("https://old.com/article")


class TestPostQueueOperations:
    """Tests for PostQueue operations."""

    def test_add_post(self, test_post_queue):
        """Should add post to queue."""
        post_id = test_post_queue.add_post(
            post_text="Test post content",
            article_url="https://example.com/article",
            article_title="Test Article",
            format_type="ai_tool"
        )
        
        assert post_id is not None
        assert post_id > 0

    def test_get_next_pending(self, test_post_queue):
        """Should return next pending post."""
        # Add post without scheduled time (should be immediately available)
        test_post_queue.add_post(
            post_text="Pending post",
            format_type="quick_tip"
        )
        
        pending = test_post_queue.get_next_pending()
        
        assert pending is not None
        assert pending["post_text"] == "Pending post"
        assert pending["status"] == "pending"

    def test_get_pending_count(self, test_post_queue):
        """Should return correct pending count."""
        # Initially empty
        assert test_post_queue.get_pending_count() == 0
        
        # Add posts
        test_post_queue.add_post(post_text="Post 1", format_type="ai_tool")
        test_post_queue.add_post(post_text="Post 2", format_type="quick_tip")
        
        assert test_post_queue.get_pending_count() == 2

    def test_mark_published(self, test_post_queue):
        """Should mark post as published."""
        post_id = test_post_queue.add_post(
            post_text="To be published",
            format_type="ai_tool"
        )
        
        test_post_queue.mark_published(post_id)
        
        # Should not be in pending anymore
        pending = test_post_queue.get_next_pending()
        if pending:
            assert pending["id"] != post_id

    def test_mark_failed(self, test_post_queue):
        """Should mark post as failed with error message."""
        post_id = test_post_queue.add_post(
            post_text="Will fail",
            format_type="ai_tool"
        )
        
        test_post_queue.mark_failed(post_id, "Test error message")
        
        # Should not be in pending anymore
        pending = test_post_queue.get_next_pending()
        if pending:
            assert pending["id"] != post_id


class TestPostQueueScheduling:
    """Tests for PostQueue scheduling features."""

    def test_schedule_posts_for_day(self, test_post_queue):
        """Should schedule multiple posts for specific times."""
        posts = [
            {"text": "Morning post", "format": "ai_tool"},
            {"text": "Noon post", "format": "quick_tip"},
            {"text": "Evening post", "format": "prompt_day"},
        ]
        
        post_ids = test_post_queue.schedule_posts_for_day(
            posts,
            times=["09:00", "12:00", "18:00"]
        )
        
        assert len(post_ids) == 3
        assert all(pid > 0 for pid in post_ids)

    def test_scheduled_post_not_available_early(self, test_post_queue):
        """Future scheduled posts should not be returned."""
        from datetime import datetime, timedelta
        
        future_time = datetime.now() + timedelta(hours=24)
        
        test_post_queue.add_post(
            post_text="Future post",
            format_type="ai_tool",
            scheduled_at=future_time
        )
        
        pending = test_post_queue.get_next_pending()
        
        # Should not return future post
        if pending:
            assert pending["post_text"] != "Future post"

    def test_get_posts_for_today(self, test_post_queue):
        """Should return posts scheduled for today."""
        from datetime import datetime
        
        today = datetime.now().replace(hour=23, minute=59)
        
        test_post_queue.add_post(
            post_text="Today's post",
            format_type="ai_tool",
            scheduled_at=today
        )
        
        posts = test_post_queue.get_posts_for_today()
        
        assert len(posts) >= 1
        assert any(p["post_text"] == "Today's post" for p in posts)


class TestPostQueueStats:
    """Tests for PostQueue statistics."""

    def test_get_stats_empty(self, test_post_queue):
        """Stats should work on empty queue."""
        stats = test_post_queue.get_stats()
        
        assert stats.get("pending", 0) == 0
        assert stats.get("published_today", 0) == 0

    def test_get_stats_with_data(self, test_post_queue):
        """Stats should reflect actual data."""
        test_post_queue.add_post(post_text="Post 1", format_type="ai_tool")
        test_post_queue.add_post(post_text="Post 2", format_type="quick_tip")
        
        stats = test_post_queue.get_stats()
        
        assert stats.get("pending", 0) == 2

    def test_cleanup_old_posts(self, test_post_queue, temp_db_path):
        """Should clean up old published posts."""
        import sqlite3
        
        # Insert old published post directly
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("""
                INSERT INTO post_queue 
                (post_text, format, status, created_at)
                VALUES (?, ?, ?, datetime('now', '-60 days'))
            """, ("Old post", "ai_tool", "published"))
            conn.commit()
        
        # Cleanup
        deleted = test_post_queue.cleanup_old_posts(days=30)
        
        assert deleted >= 1

    def test_retry_failed_posts(self, test_post_queue):
        """Should reset failed posts to pending."""
        post_id = test_post_queue.add_post(
            post_text="Failed post",
            format_type="ai_tool"
        )
        test_post_queue.mark_failed(post_id, "Test error")
        
        reset_count = test_post_queue.retry_failed_posts()
        
        assert reset_count >= 1
        
        # Should be pending again
        assert test_post_queue.get_pending_count() >= 1
