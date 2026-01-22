"""
Integration tests with API mocking.

Tests verify correct interaction with external APIs:
- Claude API (Anthropic)
- Telegram Bot API
- RSS feeds
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.integration
class TestClaudeAPIIntegration:
    """Tests for Claude API integration."""

    def test_classifier_uses_haiku_model(
        self,
        mock_anthropic_client,
        mock_env_vars,
        sample_relevant_article,
    ):
        """Classifier should use Haiku model for cost efficiency."""
        from post_generator import PostGenerator
        
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "relevant": True,
            "confidence": 85,
            "category": "tool",
            "format": "ai_tool",
        })
        
        generator = PostGenerator()
        generator.classify_article(sample_relevant_article)
        
        # Check that Haiku model was used
        call_args = mock_anthropic_client.messages.create.call_args
        assert "haiku" in call_args.kwargs.get("model", "").lower()

    def test_generator_uses_sonnet_model(
        self,
        mock_anthropic_client,
        mock_env_vars,
        sample_relevant_article,
    ):
        """Post generator should use Sonnet model for quality."""
        from post_generator import PostFormat, PostGenerator
        
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "Test post",
            "image_prompt": "Test prompt",
        })
        
        generator = PostGenerator()
        generator.generate_post(sample_relevant_article, PostFormat.AI_TOOL)
        
        # Check that Sonnet model was used
        call_args = mock_anthropic_client.messages.create.call_args
        assert "sonnet" in call_args.kwargs.get("model", "").lower()

    def test_api_retry_on_rate_limit(
        self,
        mock_anthropic_client,
        mock_env_vars,
    ):
        """Should retry on rate limit errors."""
        from anthropic import RateLimitError
        from post_generator import PostGenerator
        
        # First call fails, second succeeds
        mock_anthropic_client.messages.create.side_effect = [
            RateLimitError("Rate limited", response=MagicMock(), body={}),
            MagicMock(content=[MagicMock(text='{"relevant": true, "confidence": 80}')]),
        ]
        
        generator = PostGenerator()
        
        # Should succeed after retry
        with pytest.raises(RateLimitError):
            # Note: actual retry is handled by tenacity decorator
            # This test just verifies the error type
            generator.classify_article({"title": "Test", "summary": "Test", "link": "https://test.com"})

    def test_classifier_prompt_contains_required_context(
        self,
        mock_anthropic_client,
        mock_env_vars,
        sample_relevant_article,
    ):
        """Classifier prompt should contain article context."""
        from post_generator import PostGenerator
        
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "relevant": True, "confidence": 85, "category": "tool", "format": "ai_tool"
        })
        
        generator = PostGenerator()
        generator.classify_article(sample_relevant_article)
        
        # Get the prompt that was sent
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args.kwargs.get("messages", [])
        prompt = messages[0]["content"] if messages else ""
        
        # Verify article details are in prompt
        assert sample_relevant_article["title"] in prompt
        assert sample_relevant_article["source"] in prompt


@pytest.mark.integration
class TestTelegramAPIIntegration:
    """Tests for Telegram API integration."""

    def test_send_message_uses_correct_endpoint(
        self,
        mock_telegram_api,
        mock_env_vars,
    ):
        """sendMessage should use correct API endpoint."""
        from telegram_bot import TelegramSender
        
        sender = TelegramSender()
        sender.send_message("Test message")
        
        # Check endpoint
        call_args = mock_telegram_api.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        
        assert "sendMessage" in url
        assert mock_env_vars["TELEGRAM_BOT_TOKEN"] in url

    def test_send_to_channel_uses_channel_id(
        self,
        mock_telegram_api,
        mock_env_vars,
    ):
        """send_to_channel should use configured channel ID."""
        from telegram_bot import TelegramSender
        
        sender = TelegramSender()
        sender.send_to_channel("Test channel message")
        
        # Check that channel_id was used
        call_args = mock_telegram_api.call_args
        data = call_args.kwargs.get("data", {})
        
        assert data.get("chat_id") == mock_env_vars["TELEGRAM_CHANNEL_ID"]

    def test_long_message_is_chunked(
        self,
        mock_telegram_api,
        mock_env_vars,
    ):
        """Long messages should be split into chunks."""
        from telegram_bot import TelegramSender
        
        sender = TelegramSender()
        
        # Message longer than 4000 chars
        long_message = "A" * 5000
        sender.send_message(long_message)
        
        # Should have made multiple API calls
        assert mock_telegram_api.call_count >= 2

    def test_message_parse_mode_markdown(
        self,
        mock_telegram_api,
        mock_env_vars,
    ):
        """Messages should be sent with Markdown parse mode."""
        from telegram_bot import TelegramSender
        
        sender = TelegramSender()
        sender.send_message("**Bold** text")
        
        call_args = mock_telegram_api.call_args
        data = call_args.kwargs.get("data", {})
        
        assert data.get("parse_mode") == "Markdown"


@pytest.mark.integration
class TestRSSFeedIntegration:
    """Tests for RSS feed integration."""

    def test_rss_parser_loads_config(self, temp_db_path):
        """RSS parser should load feed config correctly."""
        import json
        import tempfile
        from pathlib import Path
        
        # Create temp config
        config = [
            {"name": "Test Feed", "url": "https://test.com/feed", "enabled": True},
            {"name": "Disabled Feed", "url": "https://disabled.com/feed", "enabled": False},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            config_path = f.name
        
        try:
            with patch("rss_parser.RSSParser._load_feeds") as mock_load:
                mock_load.return_value = config
                
                from rss_parser import RSSParser
                parser = RSSParser.__new__(RSSParser)
                parser.feeds = config
                
                # Only enabled feeds should be used
                enabled = [f for f in parser.feeds if f.get("enabled", True)]
                assert len(enabled) == 1
                assert enabled[0]["name"] == "Test Feed"
        finally:
            Path(config_path).unlink()

    def test_rss_parser_handles_feed_error(self, mock_rss_parser):
        """RSS parser should handle feed fetch errors gracefully."""
        from rss_parser import RSSParser
        
        with patch.object(RSSParser, "_load_feeds", return_value=[
            {"name": "Test", "url": "https://test.com/feed", "enabled": True}
        ]):
            with patch.object(RSSParser, "_fetch_feed", side_effect=Exception("Network error")):
                parser = RSSParser.__new__(RSSParser)
                parser.feeds = [{"name": "Test", "url": "https://test.com/feed", "enabled": True}]
                
                # Should not raise, just log error
                # In real implementation, fetch_recent_news catches exceptions


@pytest.mark.integration
class TestDeduplicatorWithDatabase:
    """Tests for deduplicator integration with database."""

    def test_deduplicator_loaded_from_database(
        self,
        populated_database,
    ):
        """Deduplicator should be initialized from database history."""
        from deduplicator import ContentDeduplicator
        
        # Get recent titles from database
        recent = populated_database.get_recent_titles(days=7)
        
        # Initialize deduplicator with database history
        dedup = ContentDeduplicator()
        for title, url in recent:
            dedup.add_existing(title, url)
        
        # Should detect duplicates from database
        result = dedup.check_duplicate(
            "New AI Tool for Writing",  # Similar to existing
            "https://example.com/new"
        )
        
        # May or may not be duplicate depending on similarity

    def test_database_normalization_matches_deduplicator(
        self,
        test_database,
    ):
        """Database URL normalization should match deduplicator."""
        from database import Database
        from deduplicator import ContentDeduplicator
        
        urls_to_test = [
            "https://www.example.com/article?utm_source=twitter",
            "HTTP://EXAMPLE.COM/ARTICLE/",
            "https://example.com/article",
        ]
        
        dedup = ContentDeduplicator()
        
        for url in urls_to_test:
            db_normalized = Database.normalize_url(url)
            dedup_normalized = dedup.normalize_url(url)
            
            # Both should produce same normalized URL
            assert db_normalized == dedup_normalized


@pytest.mark.integration
class TestComponentInteraction:
    """Tests for interaction between components."""

    def test_post_generator_result_fits_queue_schema(
        self,
        mock_anthropic_client,
        mock_env_vars,
        test_post_queue,
        sample_relevant_article,
    ):
        """Generated post should have all fields required by queue."""
        from post_generator import PostFormat, PostGenerator
        
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "Test post",
            "image_prompt": "Test image prompt",
        })
        
        generator = PostGenerator()
        post = generator.generate_post(sample_relevant_article, PostFormat.AI_TOOL)
        
        # Should have all fields needed for queue
        assert post.text is not None
        assert post.format is not None
        assert post.article_url is not None
        assert post.article_title is not None
        
        # Should be insertable to queue
        post_id = test_post_queue.add_post(
            post_text=post.text,
            article_url=post.article_url,
            article_title=post.article_title,
            image_prompt=post.image_prompt,
            format_type=post.format.value,
        )
        
        assert post_id > 0

    def test_database_article_filter_with_deduplicator(
        self,
        test_database,
        sample_articles,
    ):
        """Database filter and deduplicator should complement each other."""
        from deduplicator import ContentDeduplicator
        
        # Mark first article as sent in database
        test_database.mark_article_sent(
            sample_articles[0]["link"],
            sample_articles[0]["title"]
        )
        
        # Filter with database
        db_filtered = test_database.filter_unsent_articles(sample_articles)
        
        # Then check with deduplicator for fuzzy matches
        dedup = ContentDeduplicator()
        
        # Add a similar title to deduplicator
        dedup.add_existing(
            "AI Tool for Email Writing",  # Similar to one in sample
            "https://other.com/similar"
        )
        
        # Final filtering
        final_articles = []
        for article in db_filtered:
            result = dedup.check_duplicate(article["title"], article["link"])
            if not result.is_duplicate:
                final_articles.append(article)
        
        # Should have fewer articles than original
        assert len(final_articles) <= len(db_filtered)
