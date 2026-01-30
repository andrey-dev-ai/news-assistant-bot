"""RSS feed parser for collecting AI news."""

import json
import re
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


def extract_image_from_entry(entry) -> Optional[str]:
    """
    Extract image URL from RSS entry.

    Tries multiple sources:
    1. media:content (most common for news sites)
    2. media:thumbnail
    3. enclosure (for podcasts/media)
    4. Image in HTML content/summary

    Args:
        entry: feedparser entry object

    Returns:
        Image URL or None
    """
    # Try media:content (common in news RSS)
    if hasattr(entry, "media_content") and entry.media_content:
        for media in entry.media_content:
            if media.get("type", "").startswith("image") or media.get("medium") == "image":
                return media.get("url")
        # Sometimes media_content has no type but still an image
        if entry.media_content[0].get("url"):
            url = entry.media_content[0]["url"]
            if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                return url

    # Try media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url")

    # Try enclosure
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")

    # Try to extract from HTML content/summary
    content = entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
    summary = entry.get("summary", "")

    for html_content in [content, summary]:
        if html_content:
            # Find img tags
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content)
            if img_match:
                url = img_match.group(1)
                # Skip tracking pixels and icons
                if not any(skip in url.lower() for skip in ["pixel", "tracking", "icon", "logo", "1x1"]):
                    return url

    return None


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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
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

                    # Extract image from RSS entry
                    image_url = extract_image_from_entry(entry)

                    article = {
                        "title": entry.get("title", "No title"),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": pub_date.isoformat() if pub_date else None,
                        "source": feed["name"],
                        "image_url": image_url,  # From RSS (may be None)
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

    def enrich_with_og_images(self, articles: List[Dict], max_workers: int = 3) -> List[Dict]:
        """
        Enrich articles that don't have images with og:image from their pages.

        This is slower (makes HTTP requests) so use sparingly.

        Args:
            articles: List of article dicts
            max_workers: Number of parallel requests

        Returns:
            Enriched articles
        """
        try:
            from og_parser import enrich_articles_batch

            # Only enrich articles without images
            articles_without_images = [a for a in articles if not a.get("image_url")]
            articles_with_images = [a for a in articles if a.get("image_url")]

            if articles_without_images:
                logger.info(f"Enriching {len(articles_without_images)} articles with og:image...")
                enriched = enrich_articles_batch(articles_without_images, max_workers=max_workers)
                return articles_with_images + enriched

            return articles

        except ImportError:
            logger.warning("og_parser not available, skipping image enrichment")
            return articles
        except Exception as e:
            logger.error(f"Error enriching articles with og:image: {e}")
            return articles


if __name__ == "__main__":
    # Test the parser
    parser = RSSParser()
    articles = parser.fetch_recent_news(hours=24)

    print(f"\n=== Found {len(articles)} articles ===\n")

    # Count articles with images
    with_images = sum(1 for a in articles if a.get("image_url"))
    print(f"Articles with images from RSS: {with_images}/{len(articles)}\n")

    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Image: {article.get('image_url', 'None')[:60]}..." if article.get('image_url') else "   Image: None")
        print(f"   Link: {article['link']}\n")

    # Test og:image enrichment
    print("\n=== Testing og:image enrichment ===\n")
    enriched = parser.enrich_with_og_images(articles[:3])
    for i, article in enumerate(enriched, 1):
        print(f"{i}. {article['title'][:50]}...")
        print(f"   Image: {article.get('image_url', 'None')[:60]}..." if article.get('image_url') else "   Image: None")
        print()
