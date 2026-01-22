"""
Unit tests for PostGenerator module.

Tests cover:
- Classifier response parsing
- Article classification
- Post format handling
- Response format validation
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from post_generator import (
    GeneratedPost,
    PostFormat,
    PostGenerator,
    parse_classifier_response,
)


class TestParseClassifierResponse:
    """Tests for parse_classifier_response function."""

    def test_parse_valid_json(self):
        """Should parse valid JSON response."""
        response = '{"relevant": true, "confidence": 85, "category": "tool", "format": "ai_tool", "reason": "Good fit"}'
        
        result = parse_classifier_response(response)
        
        assert result["relevant"] is True
        assert result["confidence"] == 85
        assert result["category"] == "tool"
        assert result["format"] == "ai_tool"

    def test_parse_json_with_markdown_blocks(self):
        """Should handle JSON wrapped in markdown code blocks."""
        response = '''```json
{"relevant": true, "confidence": 75, "category": "tip", "format": "quick_tip", "reason": "Test"}
```'''
        
        result = parse_classifier_response(response)
        
        assert result["relevant"] is True
        assert result["confidence"] == 75

    def test_parse_json_with_extra_text(self):
        """Should extract JSON from text with extra content."""
        response = '''Here is my analysis:
{"relevant": false, "confidence": 30, "category": "enterprise", "format": "ai_tool", "reason": "B2B"}
This is not relevant for the channel.'''
        
        result = parse_classifier_response(response)
        
        assert result["relevant"] is False
        assert result["confidence"] == 30

    def test_parse_invalid_json_returns_default(self):
        """Should return default response for invalid JSON."""
        response = "This is not valid JSON at all"
        
        result = parse_classifier_response(response)
        
        assert result["relevant"] is False
        assert result["category"] == "parse_error"
        assert result["needs_review"] is True

    def test_parse_missing_required_fields(self):
        """Should return default for missing required fields."""
        response = '{"category": "tool", "format": "ai_tool"}'  # Missing relevant and confidence
        
        result = parse_classifier_response(response)
        
        assert result["relevant"] is False
        assert "Missing required fields" in result["reason"]

    def test_confidence_normalization(self):
        """Should normalize confidence to 0-100 range."""
        # Over 100
        response = '{"relevant": true, "confidence": 150, "category": "tool", "format": "ai_tool"}'
        result = parse_classifier_response(response)
        assert result["confidence"] == 100
        
        # Negative
        response = '{"relevant": true, "confidence": -10, "category": "tool", "format": "ai_tool"}'
        result = parse_classifier_response(response)
        assert result["confidence"] == 0

    def test_default_values_for_optional_fields(self):
        """Should set defaults for missing optional fields."""
        response = '{"relevant": true, "confidence": 80}'
        
        result = parse_classifier_response(response)
        
        assert result["category"] == "unknown"
        assert result["format"] == "ai_tool"
        assert result["reason"] == ""
        assert "needs_review" in result

    def test_needs_review_auto_set(self):
        """needs_review should be True if confidence < 70."""
        response = '{"relevant": true, "confidence": 65, "category": "tool", "format": "ai_tool"}'
        
        result = parse_classifier_response(response)
        
        assert result["needs_review"] is True


class TestPostFormat:
    """Tests for PostFormat enum."""

    def test_post_format_values(self):
        """PostFormat should have expected values."""
        assert PostFormat.AI_TOOL.value == "ai_tool"
        assert PostFormat.QUICK_TIP.value == "quick_tip"
        assert PostFormat.PROMPT_DAY.value == "prompt_day"
        assert PostFormat.COMPARISON.value == "comparison"
        assert PostFormat.CHECKLIST.value == "checklist"

    def test_post_format_from_string(self):
        """Should create PostFormat from string value."""
        assert PostFormat("ai_tool") == PostFormat.AI_TOOL
        assert PostFormat("quick_tip") == PostFormat.QUICK_TIP

    def test_invalid_format_raises(self):
        """Invalid format string should raise ValueError."""
        with pytest.raises(ValueError):
            PostFormat("invalid_format")


class TestGeneratedPost:
    """Tests for GeneratedPost dataclass."""

    def test_generated_post_creation(self):
        """Should create GeneratedPost correctly."""
        post = GeneratedPost(
            text="Test post text",
            format=PostFormat.AI_TOOL,
            article_url="https://example.com",
            article_title="Test Article",
            image_prompt="Flat design illustration"
        )
        
        assert post.text == "Test post text"
        assert post.format == PostFormat.AI_TOOL
        assert post.article_url == "https://example.com"
        assert post.image_prompt == "Flat design illustration"

    def test_generated_post_optional_image_prompt(self):
        """image_prompt should be optional."""
        post = GeneratedPost(
            text="Test",
            format=PostFormat.QUICK_TIP,
            article_url="https://example.com",
            article_title="Title"
        )
        
        assert post.image_prompt is None


class TestPostGeneratorClassification:
    """Tests for PostGenerator.classify_article method."""

    def test_classify_relevant_article(self, mock_anthropic_client, mock_env_vars):
        """Should classify relevant article correctly."""
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "relevant": True,
            "confidence": 85,
            "category": "tool",
            "format": "ai_tool",
            "reason": "AI tool for photo editing, free, consumer-friendly"
        })
        
        generator = PostGenerator()
        
        article = {
            "title": "Canva Launches Free AI Photo Editor",
            "summary": "New AI-powered photo editor for Instagram.",
            "source": "TechCrunch",
            "link": "https://example.com/canva"
        }
        
        result = generator.classify_article(article)
        
        assert result is not None
        assert result["relevant"] is True
        assert result["confidence"] == 85

    def test_classify_irrelevant_article(self, mock_anthropic_client, mock_env_vars):
        """Should classify irrelevant article correctly."""
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "relevant": False,
            "confidence": 90,
            "category": "enterprise",
            "format": "ai_tool",
            "reason": "B2B enterprise solution, not for consumers"
        })
        
        generator = PostGenerator()
        
        article = {
            "title": "Enterprise AI Platform for Teams",
            "summary": "New B2B solution for enterprise AI.",
            "source": "VentureBeat",
            "link": "https://example.com/enterprise"
        }
        
        result = generator.classify_article(article)
        
        assert result is not None
        assert result["relevant"] is False

    def test_classify_handles_api_error(self, mock_anthropic_client, mock_env_vars):
        """Should handle API errors gracefully."""
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")
        
        generator = PostGenerator()
        
        result = generator.classify_article({
            "title": "Test",
            "summary": "Test",
            "source": "Test",
            "link": "https://example.com"
        })
        
        assert result is None


class TestPostGeneratorGeneration:
    """Tests for PostGenerator.generate_post method."""

    def test_generate_ai_tool_post(self, mock_anthropic_client, mock_env_vars):
        """Should generate AI tool format post."""
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "AI-tool post content",
            "image_prompt": "Flat design, AI icon"
        })
        
        generator = PostGenerator()
        
        article = {
            "title": "New AI Tool",
            "summary": "Description",
            "link": "https://example.com"
        }
        
        post = generator.generate_post(article, PostFormat.AI_TOOL)
        
        assert post is not None
        assert post.format == PostFormat.AI_TOOL
        assert post.article_url == "https://example.com"

    def test_generate_quick_tip_post(self, mock_anthropic_client, mock_env_vars):
        """Should generate quick tip format post."""
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "text": "Quick tip content",
            "image_prompt": "Simple flat icon"
        })
        
        generator = PostGenerator()
        
        post = generator.generate_post(
            {"title": "Tip", "summary": "Desc", "link": "https://example.com"},
            PostFormat.QUICK_TIP
        )
        
        assert post is not None
        assert post.format == PostFormat.QUICK_TIP

    def test_generate_handles_non_json_response(self, mock_anthropic_client, mock_env_vars):
        """Should handle non-JSON response from API."""
        mock_anthropic_client.messages.create.return_value.content[0].text = "Plain text response"
        
        generator = PostGenerator()
        
        post = generator.generate_post(
            {"title": "Test", "summary": "Test", "link": "https://example.com"},
            PostFormat.AI_TOOL
        )
        
        assert post is not None
        assert post.text == "Plain text response"
        assert post.image_prompt is None


class TestPostGeneratorFiltering:
    """Tests for PostGenerator.filter_and_rank_articles method."""

    def test_filter_and_rank_articles(self, mock_anthropic_client, mock_env_vars):
        """Should filter and rank articles by confidence."""
        # Setup mock to return different responses
        responses = [
            {"relevant": True, "confidence": 90, "category": "tool", "format": "ai_tool"},
            {"relevant": False, "confidence": 30, "category": "enterprise", "format": "ai_tool"},
            {"relevant": True, "confidence": 75, "category": "tip", "format": "quick_tip"},
        ]
        
        call_count = [0]
        def side_effect(*args, **kwargs):
            response = MagicMock()
            response.content = [MagicMock(text=json.dumps(responses[call_count[0] % len(responses)]))]
            call_count[0] += 1
            return response
        
        mock_anthropic_client.messages.create.side_effect = side_effect
        
        generator = PostGenerator()
        
        articles = [
            {"title": "Article 1", "summary": "Desc 1", "link": "https://1.com"},
            {"title": "Article 2", "summary": "Desc 2", "link": "https://2.com"},
            {"title": "Article 3", "summary": "Desc 3", "link": "https://3.com"},
        ]
        
        ranked = generator.filter_and_rank_articles(articles, max_posts=5)
        
        # Should filter out irrelevant and sort by confidence
        assert len(ranked) == 2  # Only 2 relevant
        assert ranked[0][1]["confidence"] >= ranked[1][1]["confidence"]  # Sorted desc

    def test_filter_respects_confidence_threshold(self, mock_anthropic_client, mock_env_vars):
        """Should filter out articles with confidence < 60."""
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({
            "relevant": True,
            "confidence": 55,  # Below threshold
            "category": "tool",
            "format": "ai_tool"
        })
        
        generator = PostGenerator()
        
        ranked = generator.filter_and_rank_articles([
            {"title": "Low confidence", "summary": "Desc", "link": "https://example.com"}
        ])
        
        assert len(ranked) == 0  # Filtered out


class TestPostGeneratorInitialization:
    """Tests for PostGenerator initialization."""

    def test_init_without_api_key_raises(self):
        """Should raise if no API key available."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                PostGenerator()

    def test_init_with_api_key_param(self, mock_anthropic_client):
        """Should accept API key as parameter."""
        generator = PostGenerator(api_key="test_key")
        
        assert generator.api_key == "test_key"

    def test_init_from_env_var(self, mock_anthropic_client, mock_env_vars):
        """Should read API key from environment."""
        generator = PostGenerator()
        
        assert generator.api_key == mock_env_vars["ANTHROPIC_API_KEY"]
