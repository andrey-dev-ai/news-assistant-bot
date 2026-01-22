"""
Pytest configuration and shared fixtures for news-assistant-bot tests.
"""

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_database(temp_db_path: str):
    """Create a test database instance with initialized tables."""
    from database import Database
    
    # Override default path
    db = Database(db_path=temp_db_path)
    return db


@pytest.fixture
def test_post_queue(temp_db_path: str):
    """Create a test post queue instance."""
    from post_queue import PostQueue
    
    queue = PostQueue(db_path=temp_db_path)
    return queue


@pytest.fixture
def populated_database(test_database):
    """Database with sample data for testing."""
    articles = [
        ("https://example.com/ai-tool-1", "New AI Tool for Writing"),
        ("https://example.com/chatgpt-update", "ChatGPT Gets Major Update"),
        ("https://example.com/canva-ai", "Canva Launches AI Editor"),
        ("https://techcrunch.com/ai-news", "TechCrunch: AI Investment Rises"),
        ("https://example.com/dalle-3", "DALL-E 3 Now Available"),
    ]
    
    for link, title in articles:
        test_database.mark_article_sent(link, title, relevance_score=80, category="tool")
    
    return test_database


# =============================================================================
# Deduplicator Fixtures
# =============================================================================

@pytest.fixture
def deduplicator():
    """Create a fresh ContentDeduplicator instance."""
    from deduplicator import ContentDeduplicator
    
    return ContentDeduplicator(
        similarity_threshold=0.65,
        ngram_size=3,
        max_history=1000,
    )


@pytest.fixture
def populated_deduplicator(deduplicator):
    """Deduplicator with sample data for testing."""
    existing_articles = [
        ("10 AI Tools for Writing", "https://example.com/1"),
        ("ChatGPT Gets Major Update", "https://example.com/2"),
        ("Canva Launches AI Photo Editor", "https://example.com/3"),
        ("How to Use Python for Data Science", "https://example.com/4"),
        ("Best Budget Apps for Personal Finance", "https://example.com/5"),
    ]
    
    for title, url in existing_articles:
        deduplicator.add_existing(title, url)
    
    return deduplicator


# =============================================================================
# Mock Claude API Fixtures
# =============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing without API calls."""
    with patch("anthropic.Anthropic") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client
        
        # Default response for messages.create
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"relevant": true, "confidence": 85, "category": "tool", "format": "ai_tool", "reason": "Test reason"}')]
        mock_client.messages.create.return_value = mock_response
        
        yield mock_client


@pytest.fixture
def mock_classifier_response():
    """Factory fixture for creating mock classifier responses."""
    def _create_response(
        relevant: bool = True,
        confidence: int = 85,
        category: str = "tool",
        format_type: str = "ai_tool",
        reason: str = "Mock reason",
        needs_review: bool = False,
        url_check_needed: bool = False,
    ) -> str:
        return json.dumps({
            "relevant": relevant,
            "confidence": confidence,
            "category": category,
            "format": format_type,
            "reason": reason,
            "needs_review": needs_review,
            "url_check_needed": url_check_needed,
        })
    
    return _create_response


@pytest.fixture
def mock_post_generation_response():
    """Factory fixture for creating mock post generation responses."""
    def _create_response(
        text: str = "Test post text",
        image_prompt: str = "Flat design, pastel colors, AI icon",
    ) -> str:
        return json.dumps({
            "text": text,
            "image_prompt": image_prompt,
        })
    
    return _create_response


# =============================================================================
# Mock Telegram API Fixtures
# =============================================================================

@pytest.fixture
def mock_telegram_api():
    """Mock Telegram API for testing without network calls."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        yield mock_post


@pytest.fixture
def mock_telegram_sender(mock_telegram_api):
    """Create a TelegramSender with mocked API."""
    with patch.dict(os.environ, {
        "TELEGRAM_BOT_TOKEN": "test_token_123",
        "TELEGRAM_USER_ID": "12345678",
        "TELEGRAM_CHANNEL_ID": "@test_channel",
    }):
        from telegram_bot import TelegramSender
        
        sender = TelegramSender()
        yield sender


# =============================================================================
# RSS Parser Fixtures
# =============================================================================

@pytest.fixture
def mock_rss_feed():
    """Create mock RSS feed data."""
    return {
        "entries": [
            {
                "title": "New AI Tool Announcement",
                "link": "https://example.com/new-ai-tool",
                "summary": "A new AI tool for productivity was announced today.",
                "published_parsed": (2024, 1, 15, 10, 0, 0, 0, 15, 0),
            },
            {
                "title": "ChatGPT Update Released",
                "link": "https://example.com/chatgpt-update",
                "summary": "OpenAI released a major update to ChatGPT.",
                "published_parsed": (2024, 1, 15, 8, 0, 0, 0, 15, 0),
            },
            {
                "title": "AI for Business: Enterprise Solutions",
                "link": "https://example.com/enterprise-ai",
                "summary": "New B2B AI solutions for enterprise customers.",
                "published_parsed": (2024, 1, 15, 6, 0, 0, 0, 15, 0),
            },
        ]
    }


@pytest.fixture
def mock_rss_parser(mock_rss_feed):
    """Mock RSSParser for testing without network calls."""
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(**mock_rss_feed)
        
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"<xml>mock rss</xml>"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            
            yield mock_parse


# =============================================================================
# Sample Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_articles() -> List[Dict]:
    """Sample articles for testing."""
    return [
        {
            "title": "New AI Tool for Writing Emails",
            "link": "https://example.com/ai-email-tool",
            "summary": "A new AI-powered tool helps you write professional emails in seconds.",
            "source": "TechCrunch",
            "published": datetime.now().isoformat(),
        },
        {
            "title": "ChatGPT Now Has Image Generation",
            "link": "https://example.com/chatgpt-images",
            "summary": "OpenAI announced that ChatGPT can now generate images directly.",
            "source": "The Verge",
            "published": datetime.now().isoformat(),
        },
        {
            "title": "Enterprise AI Platform for Teams",
            "link": "https://example.com/enterprise-ai-platform",
            "summary": "New B2B solution for enterprise AI deployment.",
            "source": "VentureBeat",
            "published": datetime.now().isoformat(),
        },
        {
            "title": "Free AI Photo Editor for Instagram",
            "link": "https://example.com/ai-photo-editor",
            "summary": "Edit your Instagram photos with AI - completely free!",
            "source": "ProductHunt",
            "published": datetime.now().isoformat(),
        },
        {
            "title": "AI SDK for Developers Released",
            "link": "https://example.com/ai-sdk-developers",
            "summary": "New Python SDK for building AI applications.",
            "source": "GitHub Blog",
            "published": datetime.now().isoformat(),
        },
    ]


@pytest.fixture
def sample_relevant_article() -> Dict:
    """A sample article that should be classified as relevant."""
    return {
        "title": "Canva Launches Free AI Photo Editor",
        "link": "https://example.com/canva-ai",
        "summary": "Canva announced a new AI-powered photo editor that can automatically enhance photos, remove backgrounds, and suggest Instagram-ready filters. The tool is free for basic use.",
        "source": "TechCrunch",
        "published": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_irrelevant_article() -> Dict:
    """A sample article that should be classified as irrelevant."""
    return {
        "title": "New AI Framework for ML Engineers",
        "link": "https://example.com/ml-framework",
        "summary": "A new Python framework for machine learning engineers. Requires knowledge of PyTorch and TensorFlow. Enterprise pricing starts at $500/month.",
        "source": "GitHub Blog",
        "published": datetime.now().isoformat(),
    }


# =============================================================================
# Golden Test Fixtures
# =============================================================================

@pytest.fixture
def golden_tests_path() -> Path:
    """Path to golden tests data directory."""
    return Path(__file__).parent / "golden_tests" / "data"


@pytest.fixture
def anti_patterns() -> List[str]:
    """List of anti-patterns that should not appear in generated posts."""
    return [
        "нейросеть",
        "революционный",
        "уникальный",
        "лучший",
        "представляем",
        "встречайте",
        "данный",
        "является",
        "осуществляет",
        "искусственный интеллект",  # More than once is bad
    ]


@pytest.fixture
def required_post_elements() -> Dict[str, List[str]]:
    """Required elements for each post format."""
    return {
        "ai_tool": [
            "AI-находка дня",
            "Попробовать:",
        ],
        "quick_tip": [
            "Быстрый совет",
        ],
        "prompt_day": [
            "Промт дня",
            "Промт для ChatGPT",
            "Копируй и пользуйся",
        ],
    }


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "ANTHROPIC_API_KEY": "test_api_key_sk-ant-xxx",
        "TELEGRAM_BOT_TOKEN": "test_bot_token_123",
        "TELEGRAM_USER_ID": "12345678",
        "TELEGRAM_CHANNEL_ID": "@ai_dlya_mamy_test",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


# =============================================================================
# Async Test Helpers
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Test Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "golden: marks tests as golden tests"
    )
    config.addinivalue_line(
        "markers", "api: marks tests that require real API access"
    )
