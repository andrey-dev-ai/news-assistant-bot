"""Parse Open Graph images from article pages."""

import os
import re
import tempfile
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from logger import get_logger

logger = get_logger("news_bot.og_parser")

# User-Agent to avoid blocks
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Minimum image dimensions (to filter out icons/logos)
MIN_WIDTH = 400
MIN_HEIGHT = 300


def fetch_og_image(url: str, timeout: int = 10) -> Optional[str]:
    """
    Fetch og:image URL from an article page.

    Args:
        url: Article URL to parse
        timeout: Request timeout in seconds

    Returns:
        Image URL or None if not found
    """
    if not url:
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Try og:image first (most common)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]
            # Handle relative URLs
            if not image_url.startswith(("http://", "https://")):
                image_url = urljoin(url, image_url)
            logger.debug(f"Found og:image: {image_url}")
            return image_url

        # Try twitter:image as fallback
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            image_url = twitter_image["content"]
            if not image_url.startswith(("http://", "https://")):
                image_url = urljoin(url, image_url)
            logger.debug(f"Found twitter:image: {image_url}")
            return image_url

        # Try first large image in article as last resort
        article = soup.find("article") or soup.find("main") or soup
        for img in article.find_all("img", src=True):
            src = img.get("src") or img.get("data-src")
            if src and not _is_icon_or_logo(src):
                if not src.startswith(("http://", "https://")):
                    src = urljoin(url, src)
                logger.debug(f"Found article image: {src}")
                return src

        logger.debug(f"No og:image found for {url}")
        return None

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch og:image from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing og:image from {url}: {e}")
        return None


def _is_icon_or_logo(url: str) -> bool:
    """Check if URL is likely an icon or logo (not a real article image)."""
    url_lower = url.lower()
    icon_patterns = [
        "logo", "icon", "favicon", "avatar", "badge",
        "sprite", "button", "ad-", "banner", "pixel",
        ".svg", "1x1", "tracking"
    ]
    return any(pattern in url_lower for pattern in icon_patterns)


def download_image(image_url: str, save_dir: str = None, timeout: int = 15) -> Optional[str]:
    """
    Download image from URL and save locally.

    Args:
        image_url: URL of image to download
        save_dir: Directory to save image (default: data/images)
        timeout: Request timeout

    Returns:
        Path to saved image or None if failed
    """
    if not image_url:
        return None

    # Default save directory
    if save_dir is None:
        save_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "images"
        )

    # Ensure directory exists
    os.makedirs(save_dir, exist_ok=True)

    try:
        response = requests.get(image_url, headers=HEADERS, timeout=timeout, stream=True)
        response.raise_for_status()

        # Determine file extension from content-type or URL
        content_type = response.headers.get("Content-Type", "")
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            # Try to get from URL
            parsed = urlparse(image_url)
            path = parsed.path.lower()
            if ".png" in path:
                ext = ".png"
            elif ".webp" in path:
                ext = ".webp"
            elif ".gif" in path:
                ext = ".gif"
            else:
                ext = ".jpg"  # Default

        # Generate unique filename
        import hashlib
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:12]
        filename = f"og_{url_hash}{ext}"
        filepath = os.path.join(save_dir, filename)

        # Save image
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded image: {filepath}")
        return filepath

    except requests.RequestException as e:
        logger.warning(f"Failed to download image from {image_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error saving image from {image_url}: {e}")
        return None


def enrich_article_with_image(article: Dict) -> Dict:
    """
    Add image_url to article if not already present.

    Tries:
    1. RSS enclosure/media (if already in article)
    2. og:image from article page

    Args:
        article: Article dict with 'link' key

    Returns:
        Article dict with 'image_url' added (or None)
    """
    # Skip if already has image
    if article.get("image_url"):
        return article

    # Try to fetch og:image
    link = article.get("link")
    if link:
        image_url = fetch_og_image(link)
        if image_url:
            article["image_url"] = image_url
            logger.debug(f"Enriched article with image: {article.get('title', '')[:50]}")

    return article


def enrich_articles_batch(articles: list, max_workers: int = 5) -> list:
    """
    Enrich multiple articles with images in parallel.

    Args:
        articles: List of article dicts
        max_workers: Number of parallel requests

    Returns:
        List of enriched articles
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    enriched = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(enrich_article_with_image, article): article
            for article in articles
        }
        for future in as_completed(futures):
            try:
                enriched.append(future.result())
            except Exception as e:
                logger.error(f"Error enriching article: {e}")
                enriched.append(futures[future])  # Add original

    return enriched


if __name__ == "__main__":
    # Test with real article
    test_urls = [
        "https://techcrunch.com/2024/01/15/google-gemini-ultra-benchmark/",
        "https://venturebeat.com/ai/openai-gpt-store-launch/",
    ]

    for url in test_urls:
        print(f"\nTesting: {url}")
        image = fetch_og_image(url)
        print(f"og:image: {image}")

        if image:
            path = download_image(image)
            print(f"Downloaded to: {path}")
