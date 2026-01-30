"""Scheduler for running bot with 5 posts per day."""

import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import schedule
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import get_settings, validate_config
from logger import get_logger, setup_logging
from telegram_bot import TelegramBotHandler, TelegramSender


class GracefulShutdown:
    """Handle graceful shutdown signals."""

    def __init__(self):
        self.shutdown_requested = False
        self._original_handlers = {}
        self._logger = get_logger("news_bot.shutdown")

    def register_handlers(self):
        """Register signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._original_handlers[sig] = signal.signal(sig, self._handler)
                self._logger.debug(f"Registered handler for {sig.name}")
            except (OSError, ValueError) as e:
                self._logger.warning(f"Could not register handler for {sig}: {e}")

    def _handler(self, signum, frame):
        """Handle shutdown signal."""
        sig_name = signal.Signals(signum).name
        self._logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.shutdown_requested = True

    def should_shutdown(self) -> bool:
        """Check if shutdown was requested."""
        return self.shutdown_requested

    def cleanup(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (OSError, ValueError):
                pass


_shutdown_handler: Optional[GracefulShutdown] = None


def get_shutdown_handler() -> GracefulShutdown:
    """Get or create shutdown handler."""
    global _shutdown_handler
    if _shutdown_handler is None:
        _shutdown_handler = GracefulShutdown()
    return _shutdown_handler


def generate_daily_posts():
    """Generate posts for the day and add to queue."""
    from database import Database
    from deduplicator import get_deduplicator
    from post_generator import PostGenerator
    from post_queue import PostQueue
    from rss_parser import RSSParser

    logger = get_logger("news_bot.scheduler")
    logger.info("=" * 50)
    logger.info("Generating daily posts")
    logger.info("=" * 50)

    try:
        # Fetch articles
        parser = RSSParser()
        articles = parser.fetch_recent_news(hours=24)

        if not articles:
            logger.warning("No articles found")
            return

        # Initialize deduplicator with recent history from DB
        db = Database()
        dedup = get_deduplicator(similarity_threshold=0.65)

        # Load recent titles to deduplicator
        recent = db.get_recent_titles(days=7, limit=500)
        for title, url in recent:
            dedup.add_existing(title, url)
        logger.info(f"Loaded {len(recent)} recent articles to deduplicator")

        # Filter unsent articles
        unsent = db.filter_unsent_articles(articles)

        if not unsent:
            logger.warning("No new articles to process")
            return

        # Apply fuzzy deduplication
        unique_articles = []
        duplicates_found = 0

        for article in unsent:
            result = dedup.check_duplicate(
                title=article.get("title", ""),
                url=article.get("link", ""),
                content=article.get("summary", ""),
            )
            if not result.is_duplicate:
                unique_articles.append(article)
            else:
                duplicates_found += 1
                logger.debug(
                    f"Skipping duplicate: {article.get('title', '')[:50]}... "
                    f"(reason: {result.reason}, score: {result.similarity_score})"
                )

        logger.info(
            f"Deduplication: {len(unsent)} articles -> {len(unique_articles)} unique "
            f"({duplicates_found} duplicates removed)"
        )

        if not unique_articles:
            logger.warning("No unique articles after deduplication")
            return

        logger.info(f"Processing {len(unique_articles)} unique articles")

        # Enrich articles with images (OG/RSS)
        logger.info("Enriching articles with images...")
        enriched_articles = parser.enrich_with_og_images(unique_articles[:15])

        # Generate posts
        generator = PostGenerator()
        posts = generator.generate_daily_posts(enriched_articles, count=5)

        if not posts:
            logger.warning("No posts generated")
            return

        # Add to queue with schedule
        queue = PostQueue()
        times = ["09:00", "12:00", "15:00", "18:00", "21:00"]

        post_dicts = [
            {
                "text": post.text,
                "article_url": post.article_url,
                "article_title": post.article_title,
                "image_url": post.image_url,  # OG/RSS image URL
                "image_prompt": post.image_prompt,  # Fallback for AI generation
                "format": post.format.value,
            }
            for post in posts
        ]

        post_ids = queue.schedule_posts_for_day(post_dicts, times=times)
        logger.info(f"Scheduled {len(post_ids)} posts for today")

        # Mark articles as sent with classification data
        for post in posts:
            db.mark_article_sent(
                link=post.article_url,
                title=post.article_title,
                relevance_score=0,  # Will be updated when classification is passed
                category=post.format.value,
                status="published",
            )

        # Log deduplicator stats
        logger.info(f"Deduplicator stats: {dedup.get_stats()}")

    except Exception as e:
        logger.error(f"Error generating daily posts: {e}")


def publish_scheduled_post():
    """Publish the next scheduled post from queue with image."""
    from post_queue import PostQueue

    logger = get_logger("news_bot.scheduler")

    try:
        queue = PostQueue()
        post = queue.get_next_pending()

        if not post:
            logger.debug("No pending posts to publish")
            return

        logger.info(f"Publishing post {post['id']}: {post['format']}")

        # Get or prepare image
        image_path = None
        image_url = post.get("image_url")

        # Step 1: If we have OG/RSS image URL - download it
        if image_url and image_url.startswith(("http://", "https://")):
            try:
                from og_parser import download_image
                image_path = download_image(image_url)
                if image_path:
                    queue.update_image_url(post["id"], image_path)
                    logger.info(f"Downloaded OG image for post {post['id']}: {image_path}")
            except Exception as e:
                logger.warning(f"Failed to download OG image for post {post['id']}: {e}")
        elif image_url:
            # Already a local path
            image_path = image_url

        # Step 2: If still no image but have prompt - generate via AI
        if not image_path and post.get("image_prompt"):
            try:
                from image_generator import get_image_generator

                generator = get_image_generator()
                image_path = generator.generate_for_post(
                    post_id=post["id"],
                    image_prompt=post["image_prompt"],
                    category=post.get("format"),
                )
                if image_path:
                    queue.update_image_url(post["id"], image_path)
                    logger.info(f"Generated AI image for post {post['id']}: {image_path}")
            except Exception as e:
                logger.warning(f"Failed to generate AI image for post {post['id']}: {e}")
                # Continue without image

        # Send to channel
        sender = TelegramSender()

        # Send with image if available, otherwise text only (HTML for proper formatting)
        if image_path:
            success = sender.send_photo_to_channel(image_path, post["post_text"], parse_mode="HTML")
        else:
            success = sender.send_to_channel(post["post_text"], parse_mode="HTML")

        if success:
            queue.mark_published(post["id"])
            logger.info(f"Post {post['id']} published successfully")
        else:
            queue.mark_failed(post["id"], "Failed to send to channel")

    except Exception as e:
        logger.error(f"Error publishing post: {e}")


def send_digest():
    """Legacy function for backward compatibility - generates and publishes digest."""
    from ai_processor import AIProcessor
    from database import Database
    from rss_parser import RSSParser

    logger = get_logger("news_bot.scheduler")
    logger.info("=" * 50)
    logger.info("Generating digest (legacy mode)")
    logger.info("=" * 50)

    try:
        parser = RSSParser()
        ai_processor = AIProcessor()
        db = Database()
        sender = TelegramSender()

        articles = parser.fetch_recent_news(hours=24)
        if not articles:
            logger.warning("No articles found")
            return

        unsent = db.filter_unsent_articles(articles)
        if not unsent:
            logger.warning("No new articles")
            return

        digest = ai_processor.create_digest(unsent)

        # Send to user and channel
        sender.send_message(digest)
        if sender.channel_id:
            sender.send_to_channel(digest)

        for article in unsent[:20]:
            db.mark_article_sent(article["link"], article["title"])

        logger.info("Digest sent successfully")

    except Exception as e:
        logger.error(f"Error sending digest: {e}")


def run_scheduler():
    """Run the scheduler with 5 posts per day."""
    load_dotenv()
    logger = get_logger("news_bot.scheduler")
    shutdown = get_shutdown_handler()

    # Get publish times from env or use defaults
    publish_times = os.getenv("PUBLISH_TIMES", "09:00,12:00,15:00,18:00,21:00")
    times = [t.strip() for t in publish_times.split(",")]

    # Schedule daily post generation at 08:00 (before first publish)
    schedule.every().day.at("08:00").do(generate_daily_posts)
    logger.info("Scheduled daily post generation at 08:00")

    # Schedule publishing at each time
    for time_str in times:
        schedule.every().day.at(time_str).do(publish_scheduled_post)
        logger.info(f"Scheduled post publishing at {time_str}")

    # Also check for pending posts every 5 minutes
    # (in case of restarts or missed schedules)
    schedule.every(5).minutes.do(publish_scheduled_post)
    logger.info("Scheduled pending post check every 5 minutes")

    while not shutdown.should_shutdown():
        schedule.run_pending()
        # Check shutdown every 5 seconds
        for _ in range(12):
            if shutdown.should_shutdown():
                break
            time.sleep(5)

    logger.info("Scheduler stopped gracefully")


def main():
    """Main entry point with interactive bot."""
    load_dotenv()

    # Validate configuration
    try:
        validate_config()
        settings = get_settings()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        log_dir=settings.log_dir,
    )
    logger = get_logger("news_bot")

    # Register shutdown handlers
    shutdown = get_shutdown_handler()
    shutdown.register_handlers()

    logger.info("=" * 50)
    logger.info("AI News Bot Started (Phase 2)")
    logger.info("=" * 50)

    try:
        # Start scheduler in background thread
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        # Run interactive bot in main thread
        bot = TelegramBotHandler(digest_callback=send_digest)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        shutdown.cleanup()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    main()
