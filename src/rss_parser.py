"""RSS feed parser for collecting AI news."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from time import mktime
from typing import Dict, List, Optional

import feedparser
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from logger import get_logger

logger = get_logger("news_bot.rss")


class RSSParser:
    """Parse RSS feeds and collect news articles."""

    def __init__(self, config_path: str = "config/rss_feeds.json"):
        """Initialize RSS parser with config file."""
        self.config_path = Path(config_path)
        self.feeds = self._load_feeds()

    def _load_feeds(self) -> List[Dict]:
        """Load RSS feed configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (requests.RequestException, requests.Timeout, ConnectionError)
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry {retry_state.attempt_number} for RSS feed: "
            f"{retry_state.outcome.exception()}"
        ),
    )
    def _fetch_feed(self, url: str, timeout: int = 30) -> feedparser.FeedParserDict:
        """
        Fetch RSS feed with retry logic and timeout.

        Args:
            url: RSS feed URL
            timeout: Request timeout in seconds

        Returns:
            Parsed feed data
        """
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)

    def fetch_recent_news(self, hours: int = 24) -> List[Dict]:
        """
        Fetch news articles from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of news articles with metadata
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        all_articles = []

        for feed in self.feeds:
            if not feed.get("enabled", True):
                continue

            try:
                logger.info(f"Fetching from {feed['name']}...")
                parsed = self._fetch_feed(feed["url"])

                for entry in parsed.entries:
                    # Parse publication date
                    pub_date = self._parse_date(entry)

                    # Skip old articles
                    if pub_date and pub_date < cutoff_time:
                        continue

                    article = {
                        "title": entry.get("title", "No title"),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": pub_date.isoformat() if pub_date else None,
                        "source": feed["name"],
                    }
                    all_articles.append(article)

            except Exception as e:
                logger.error(f"Error fetching {feed['name']}: {e}")
                continue

        # Sort by publication date (newest first)
        all_articles.sort(
            key=lambda x: x["published"] if x["published"] else "", reverse=True
        )

        logger.info(f"Collected {len(all_articles)} articles")
        return all_articles

    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse publication date from feed entry."""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime.fromtimestamp(mktime(entry.published_parsed))
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime.fromtimestamp(mktime(entry.updated_parsed))
        return None


if __name__ == "__main__":
    # Test the parser
    parser = RSSParser()
    articles = parser.fetch_recent_news(hours=24)

    print(f"\n=== Found {len(articles)} articles ===\n")
    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Link: {article['link']}\n")
