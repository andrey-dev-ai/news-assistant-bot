"""
Integration tests for the full news processing pipeline.

Tests cover:
- RSS → classify → generate → queue pipeline
- Component interaction
- End-to-end data flow
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.mark.integration
class TestRSSToClassifyPipeline:
    """Tests for RSS parsing and classification pipeline."""

    def test_rss_articles_passed_to_classifier(
        self,
        mock_rss_parser,
        mock_anthropic_client,
        mock_env_vars,
        sample_articles,
    ):
        """Articles from RSS should be passed to classifier."""
        from post_generator import PostGenerator
        from rss_parser import RSSParser
        
        # Setup
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "relevant": True,
            "confidence": 85,
            "category": "tool",
            "format": "ai_tool",
            "reason": "Good fit"
        })
        
        generator = PostGenerator()
        
        # Classify each article
        for article in sample_articles[:3]:
            result = generator.classify_article(article)
            
            assert result is not None
            assert "relevant" in result
            assert "confidence" in result

    def test_irrelevant_articles_filtered_out(
        self,
        mock_anthropic_client,
        mock_env_vars,
        sample_articles,
    ):
        """Irrelevant articles should be filtered from pipeline."""
        from post_generator import PostGenerator
        
        # Setup - alternating relevant/irrelevant
        call_count = [0]
        def mock_response(*args, **kwargs):
            response = MagicMock()
            is_relevant = call_count[0] % 2 == 0
            response.content = [MagicMock(text=json.dumps({
                "relevant": is_relevant,
                "confidence": 85 if is_relevant else 25,
                "category": "tool" if is_relevant else "enterprise",
                "format": "ai_tool",
            }))]
            call_count[0] += 1
            return response
        
        mock_anthropic_client.messages.create.side_effect = mock_response
        
        generator = PostGenerator()
        ranked = generator.filter_and_rank_articles(sample_articles)
        
        # Only relevant articles should remain
        assert all(r[1]["relevant"] for r in ranked)


@pytest.mark.integration
class TestClassifyToGeneratePipeline:
    """Tests for classification to post generation pipeline."""

    def test_classified_articles_generate_posts(
        self,
        mock_anthropic_client,
        mock_env_vars,
        sample_relevant_article,
    ):
        """Classified articles should generate valid posts."""
        from post_generator import PostFormat, PostGenerator
        
        # Mock classification
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "🤖 AI-находка дня: Test\n\nОписание.\n\n✅ Попробовать: https://example.com",
            "image_prompt": "Flat design AI icon"
        })
        
        generator = PostGenerator()
        post = generator.generate_post(sample_relevant_article, PostFormat.AI_TOOL)
        
        assert post is not None
        assert post.format == PostFormat.AI_TOOL
        assert post.article_url == sample_relevant_article["link"]

    def test_format_selection_from_classification(
        self,
        mock_anthropic_client,
        mock_env_vars,
    ):
        """Post format should match classification recommendation."""
        from post_generator import PostFormat, PostGenerator
        
        # Classification returns quick_tip format
        responses = [
            json.dumps({
                "relevant": True,
                "confidence": 80,
                "category": "tip",
                "format": "quick_tip",
            }),
            json.dumps({
                "text": "⚡ Быстрый совет\n\nТест",
                "image_prompt": "Tip icon"
            })
        ]
        call_idx = [0]
        
        def mock_response(*args, **kwargs):
            response = MagicMock()
            response.content = [MagicMock(text=responses[min(call_idx[0], len(responses)-1)])]
            call_idx[0] += 1
            return response
        
        mock_anthropic_client.messages.create.side_effect = mock_response
        
        generator = PostGenerator()
        
        article = {
            "title": "ChatGPT Tip",
            "summary": "A quick tip for ChatGPT",
            "link": "https://example.com/tip",
            "source": "Reddit"
        }
        
        classification = generator.classify_article(article)
        assert classification["format"] == "quick_tip"


@pytest.mark.integration
class TestGenerateToQueuePipeline:
    """Tests for post generation to queue pipeline."""

    def test_generated_posts_added_to_queue(
        self,
        mock_anthropic_client,
        mock_env_vars,
        test_post_queue,
        sample_relevant_article,
    ):
        """Generated posts should be added to queue."""
        from post_generator import PostFormat, PostGenerator
        
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "🤖 AI-находка дня: Test\n\nОписание.\n\n✅ Попробовать: https://example.com",
            "image_prompt": "AI icon"
        })
        
        generator = PostGenerator()
        post = generator.generate_post(sample_relevant_article, PostFormat.AI_TOOL)
        
        # Add to queue
        post_id = test_post_queue.add_post(
            post_text=post.text,
            article_url=post.article_url,
            article_title=post.article_title,
            image_prompt=post.image_prompt,
            format_type=post.format.value,
        )
        
        assert post_id is not None
        
        # Verify in queue
        pending = test_post_queue.get_next_pending()
        assert pending is not None
        assert pending["article_url"] == sample_relevant_article["link"]

    def test_scheduled_posts_in_queue(
        self,
        mock_anthropic_client,
        mock_env_vars,
        test_post_queue,
    ):
        """Posts should be scheduled at correct times."""
        from post_generator import PostFormat, PostGenerator
        
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "Test post",
            "image_prompt": "Icon"
        })
        
        posts = [
            {"text": f"Post {i}", "article_url": f"https://example.com/{i}", 
             "article_title": f"Title {i}", "format": "ai_tool"}
            for i in range(3)
        ]
        
        times = ["09:00", "12:00", "18:00"]
        post_ids = test_post_queue.schedule_posts_for_day(posts, times=times)
        
        assert len(post_ids) == 3
        
        # Check scheduled times
        today_posts = test_post_queue.get_posts_for_today()
        assert len(today_posts) >= 3


@pytest.mark.integration
class TestFullPipeline:
    """Tests for complete RSS → classify → generate → queue → publish pipeline."""

    def test_full_daily_generation_pipeline(
        self,
        mock_anthropic_client,
        mock_env_vars,
        test_database,
        test_post_queue,
        sample_articles,
    ):
        """Full pipeline should process articles and fill queue."""
        from post_generator import PostGenerator
        
        # Setup classification responses
        classify_responses = [
            {"relevant": True, "confidence": 90, "category": "tool", "format": "ai_tool"},
            {"relevant": False, "confidence": 20, "category": "enterprise", "format": "ai_tool"},
            {"relevant": True, "confidence": 75, "category": "tip", "format": "quick_tip"},
            {"relevant": True, "confidence": 85, "category": "tool", "format": "ai_tool"},
            {"relevant": False, "confidence": 15, "category": "developer", "format": "ai_tool"},
        ]
        
        generate_response = {
            "text": "🤖 AI-находка дня: Test\n\nОписание.\n\n✅ Попробовать: https://example.com",
            "image_prompt": "AI icon"
        }
        
        call_count = [0]
        def mock_response(*args, **kwargs):
            response = MagicMock()
            if call_count[0] < len(classify_responses):
                response.content = [MagicMock(text=json.dumps(classify_responses[call_count[0]]))]
            else:
                response.content = [MagicMock(text=json.dumps(generate_response))]
            call_count[0] += 1
            return response
        
        mock_anthropic_client.messages.create.side_effect = mock_response
        
        generator = PostGenerator()
        
        # Step 1: Filter unsent articles
        unsent = test_database.filter_unsent_articles(sample_articles)
        assert len(unsent) == len(sample_articles)  # All unsent initially
        
        # Step 2: Classify and rank
        ranked = generator.filter_and_rank_articles(unsent, max_posts=5)
        assert len(ranked) <= 5
        assert all(r[1]["relevant"] for r in ranked)
        
        # Step 3: Generate posts for top articles
        posts = generator.generate_daily_posts(unsent, count=3)
        
        # Step 4: Add to queue
        for post in posts:
            test_post_queue.add_post(
                post_text=post.text,
                article_url=post.article_url,
                article_title=post.article_title,
                format_type=post.format.value,
            )
        
        # Step 5: Mark articles as sent
        for post in posts:
            test_database.mark_article_sent(
                post.article_url,
                post.article_title,
                relevance_score=85,
                category="tool"
            )
        
        # Verify queue has posts
        queue_count = test_post_queue.get_pending_count()
        assert queue_count >= len(posts)
        
        # Verify articles marked as sent
        for post in posts:
            assert test_database.is_article_sent(post.article_url)

    def test_deduplication_in_pipeline(
        self,
        mock_anthropic_client,
        mock_env_vars,
        test_database,
        populated_deduplicator,
        sample_articles,
    ):
        """Pipeline should respect deduplication."""
        # Add one article as already processed
        test_database.mark_article_sent(
            sample_articles[0]["link"],
            sample_articles[0]["title"]
        )
        
        # Check that duplicate is detected by database
        unsent = test_database.filter_unsent_articles(sample_articles)
        
        assert len(unsent) == len(sample_articles) - 1
        assert all(a["link"] != sample_articles[0]["link"] for a in unsent)


@pytest.mark.integration
class TestQueueToPublishPipeline:
    """Tests for queue to Telegram publish pipeline."""

    def test_pending_post_retrieved_and_published(
        self,
        test_post_queue,
        mock_telegram_sender,
    ):
        """Pending posts should be retrievable and publishable."""
        # Add post to queue
        post_id = test_post_queue.add_post(
            post_text="🤖 AI-находка дня: Test\n\nОписание.\n\n✅ Попробовать: https://example.com",
            article_url="https://example.com/test",
            article_title="Test Article",
            format_type="ai_tool",
        )
        
        # Get pending
        pending = test_post_queue.get_next_pending()
        assert pending is not None
        assert pending["id"] == post_id
        
        # Simulate publish
        success = mock_telegram_sender.send_to_channel(pending["post_text"])
        
        if success:
            test_post_queue.mark_published(post_id)
        
        # Verify status changed
        next_pending = test_post_queue.get_next_pending()
        if next_pending:
            assert next_pending["id"] != post_id

    def test_publish_failure_marks_as_failed(
        self,
        test_post_queue,
        mock_telegram_api,
    ):
        """Failed publish should mark post as failed."""
        # Setup failure
        mock_telegram_api.return_value.ok = False
        mock_telegram_api.return_value.json.return_value = {"ok": False, "error": "Test error"}
        
        post_id = test_post_queue.add_post(
            post_text="Test post",
            format_type="ai_tool",
        )
        
        # Simulate failed publish
        test_post_queue.mark_failed(post_id, "Telegram API error")
        
        # Verify
        pending = test_post_queue.get_next_pending()
        if pending:
            assert pending["id"] != post_id


@pytest.mark.integration
class TestMonitoringIntegration:
    """Tests for monitoring and statistics integration."""

    def test_stats_updated_after_pipeline_run(
        self,
        test_database,
        test_post_queue,
        sample_articles,
    ):
        """Statistics should update after pipeline operations."""
        # Initial stats
        initial_db_stats = test_database.get_stats()
        initial_queue_stats = test_post_queue.get_stats()
        
        # Process some articles
        for article in sample_articles[:2]:
            test_database.mark_article_sent(
                article["link"],
                article["title"],
                relevance_score=80,
                category="tool"
            )
            test_post_queue.add_post(
                post_text=f"Post for {article['title']}",
                article_url=article["link"],
                format_type="ai_tool",
            )
        
        # Check stats updated
        final_db_stats = test_database.get_stats()
        final_queue_stats = test_post_queue.get_stats()
        
        assert final_db_stats["total_articles"] > initial_db_stats["total_articles"]
        assert final_queue_stats.get("pending", 0) > initial_queue_stats.get("pending", 0)

    def test_queue_health_reflects_state(self, test_post_queue):
        """Queue health should accurately reflect current state."""
        from datetime import datetime, timedelta
        
        # Empty queue - should be critical
        stats = test_post_queue.get_stats()
        
        # Add scheduled posts
        future_time = datetime.now() + timedelta(hours=1)
        for i in range(10):
            test_post_queue.add_post(
                post_text=f"Scheduled post {i}",
                format_type="ai_tool",
                scheduled_at=future_time + timedelta(hours=i),
            )
        
        stats = test_post_queue.get_stats()
        assert stats.get("scheduled_future", 0) >= 10
