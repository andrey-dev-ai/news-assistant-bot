#!/usr/bin/env python3
"""Аудит OG-картинок из RSS-источников.

Проверяет каждый RSS-фид: парсит последние статьи,
извлекает OG-изображения, проверяет их размер и доступность.
Выдаёт рейтинг источников по качеству картинок.
"""

import json
import re
import sys
import time
from urllib.parse import urlparse

import feedparser
import requests

FEEDS_PATH = "config/rss_feeds.json"
ARTICLES_PER_FEED = 10
TIMEOUT = 15


def load_feeds():
    with open(FEEDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_image_from_rss_entry(entry):
    """Try to get image URL from RSS entry metadata."""
    # 1. media:content
    media = entry.get("media_content", [])
    for m in media:
        url = m.get("url", "")
        if url and any(ext in url.lower() for ext in [".jpg", ".png", ".webp", ".jpeg"]):
            return url

    # 2. media:thumbnail
    thumb = entry.get("media_thumbnail", [])
    for t in thumb:
        url = t.get("url", "")
        if url:
            return url

    # 3. enclosure
    enclosures = entry.get("enclosures", [])
    for enc in enclosures:
        if enc.get("type", "").startswith("image/"):
            return enc.get("href", "")

    # 4. <img> in content/summary
    content = entry.get("content", [{}])
    html = ""
    if content and isinstance(content, list):
        html = content[0].get("value", "")
    if not html:
        html = entry.get("summary", "")

    if html:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)

    return None


def fetch_og_image(url):
    """Fetch page and extract og:image meta tag."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KLYMOBot/1.0)"
        }
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text[:50000]  # first 50KB is enough

        # og:image
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.IGNORECASE
            )
        if match:
            return match.group(1)

        # twitter:image fallback
        match = re.search(
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
                html, re.IGNORECASE
            )
        if match:
            return match.group(1)

    except Exception as e:
        return None

    return None


def check_image_quality(image_url):
    """HEAD request to check image size and content type."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KLYMOBot/1.0)"
        }
        resp = requests.head(image_url, headers=headers, timeout=TIMEOUT, allow_redirects=True)

        content_type = resp.headers.get("Content-Type", "")
        content_length = int(resp.headers.get("Content-Length", 0))

        is_image = "image" in content_type
        size_kb = content_length / 1024 if content_length else 0

        return {
            "url": image_url,
            "is_image": is_image,
            "content_type": content_type,
            "size_kb": round(size_kb, 1),
            "status": resp.status_code,
        }
    except Exception as e:
        return {
            "url": image_url,
            "is_image": False,
            "content_type": "error",
            "size_kb": 0,
            "status": 0,
            "error": str(e),
        }


def is_generic_placeholder(url):
    """Heuristic: detect generic/placeholder images."""
    url_lower = url.lower()
    generic_patterns = [
        "placeholder", "default", "logo", "favicon", "icon",
        "blank", "empty", "noimage", "no-image", "missing",
        "1x1", "pixel", "spacer",
    ]
    for p in generic_patterns:
        if p in url_lower:
            return True

    # Very small images are likely placeholders
    return False


def audit_feed(feed_info):
    """Audit a single RSS feed for OG image quality."""
    name = feed_info["name"]
    url = feed_info["url"]
    enabled = feed_info.get("enabled", True)

    if not enabled:
        return {"name": name, "status": "disabled", "articles": 0}

    print(f"\n{'='*60}")
    print(f"📡 {name}")
    print(f"   {url}")

    try:
        feed = feedparser.parse(url)
        entries = feed.entries[:ARTICLES_PER_FEED]
    except Exception as e:
        print(f"   ❌ Feed parse error: {e}")
        return {"name": name, "status": "feed_error", "articles": 0}

    if not entries:
        print(f"   ❌ No entries found")
        return {"name": name, "status": "empty", "articles": 0}

    print(f"   📰 Статей: {len(entries)}")

    results = {
        "name": name,
        "status": "ok",
        "articles": len(entries),
        "has_rss_image": 0,
        "has_og_image": 0,
        "has_any_image": 0,
        "avg_size_kb": 0,
        "large_images": 0,  # >50KB = likely good quality
        "samples": [],
    }

    sizes = []

    for i, entry in enumerate(entries):
        title = entry.get("title", "???")[:60]
        link = entry.get("link", "")

        # Step 1: check RSS image
        rss_img = extract_image_from_rss_entry(entry)
        og_img = None
        final_img = None

        if rss_img:
            results["has_rss_image"] += 1
            final_img = rss_img

        # Step 2: fetch OG image from page (only first 5 to save time)
        if i < 5 and link:
            og_img = fetch_og_image(link)
            if og_img:
                results["has_og_image"] += 1
                if not final_img:
                    final_img = og_img
            time.sleep(0.3)  # be polite

        if final_img:
            results["has_any_image"] += 1

            # Step 3: check image quality
            if not is_generic_placeholder(final_img):
                quality = check_image_quality(final_img)
                if quality["size_kb"] > 0:
                    sizes.append(quality["size_kb"])
                if quality["size_kb"] > 50:
                    results["large_images"] += 1

                if len(results["samples"]) < 3:
                    results["samples"].append({
                        "title": title,
                        "image_url": final_img[:120],
                        "size_kb": quality["size_kb"],
                        "source": "rss" if rss_img else "og",
                    })

        status = "✅" if final_img else "❌"
        src = "(rss)" if rss_img else "(og)" if og_img else ""
        size_info = ""
        if final_img and sizes:
            size_info = f" [{sizes[-1]}KB]" if sizes[-1] > 0 else ""
        print(f"   {status} {title} {src}{size_info}")

    results["avg_size_kb"] = round(sum(sizes) / len(sizes), 1) if sizes else 0
    results["image_rate"] = round(results["has_any_image"] / len(entries) * 100)

    return results


def main():
    feeds = load_feeds()
    print(f"🔍 Аудит OG-картинок: {len(feeds)} источников")
    print(f"   По {ARTICLES_PER_FEED} статей из каждого\n")

    all_results = []

    for feed_info in feeds:
        result = audit_feed(feed_info)
        all_results.append(result)

    # Summary report
    print("\n" + "=" * 70)
    print("📊 РЕЙТИНГ ИСТОЧНИКОВ ПО КАЧЕСТВУ КАРТИНОК")
    print("=" * 70)

    # Sort by: image_rate DESC, avg_size DESC
    scored = [r for r in all_results if r.get("status") == "ok"]
    scored.sort(key=lambda r: (r.get("image_rate", 0), r.get("avg_size_kb", 0)), reverse=True)

    print(f"\n{'Источник':<30} {'Статей':>7} {'С карт.':>8} {'%':>5} {'Ср.размер':>10} {'Крупных':>8}")
    print("-" * 70)

    for r in scored:
        rate = r.get("image_rate", 0)
        grade = "🟢" if rate >= 80 else "🟡" if rate >= 50 else "🔴"
        print(
            f"{grade} {r['name']:<28} {r['articles']:>5} "
            f"{r.get('has_any_image', 0):>7} {rate:>4}% "
            f"{r.get('avg_size_kb', 0):>8.1f}KB "
            f"{r.get('large_images', 0):>7}"
        )

    # Print samples from top sources
    print("\n" + "=" * 70)
    print("🖼  ПРИМЕРЫ КАРТИНОК ИЗ ЛУЧШИХ ИСТОЧНИКОВ")
    print("=" * 70)

    for r in scored[:7]:
        if r.get("samples"):
            print(f"\n📡 {r['name']}:")
            for s in r["samples"]:
                print(f"   [{s['size_kb']}KB] {s['title']}")
                print(f"   → {s['image_url']}")

    # Recommendations
    print("\n" + "=" * 70)
    print("💡 РЕКОМЕНДАЦИИ")
    print("=" * 70)

    good = [r["name"] for r in scored if r.get("image_rate", 0) >= 80 and r.get("avg_size_kb", 0) > 30]
    ok = [r["name"] for r in scored if 50 <= r.get("image_rate", 0) < 80]
    bad = [r["name"] for r in scored if r.get("image_rate", 0) < 50]

    print(f"\n🟢 Отличные картинки (использовать OG): {', '.join(good) if good else 'нет'}")
    print(f"🟡 Средние (OG + fallback генерация): {', '.join(ok) if ok else 'нет'}")
    print(f"🔴 Плохие/нет картинок (только генерация): {', '.join(bad) if bad else 'нет'}")


if __name__ == "__main__":
    main()
