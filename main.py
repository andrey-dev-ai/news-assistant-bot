"""Main script for AI News Assistant Bot."""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ai_processor import AIProcessor
from config import get_settings, validate_config
from database import Database
from logger import get_logger, setup_logging
from rss_parser import RSSParser
from telegram_bot import TelegramSender


def send_digest():
    """Collect news, process with AI, and send to Telegram."""
    logger = get_logger("news_bot")

    logger.info("=" * 50)
    logger.info("Starting AI News Digest Bot")
    logger.info("=" * 50)

    try:
        # Initialize components
        logger.info("1. Initializing components...")
        parser = RSSParser()
        ai_processor = AIProcessor()
        telegram = TelegramSender()
        db = Database()

        # Fetch recent news
        logger.info("2. Fetching news from RSS feeds...")
        articles = parser.fetch_recent_news(hours=24)

        if not articles:
            logger.info("No articles found.")
            telegram.send_message("📭 Нет новых статей за последние 24 часа.")
            return

        # Filter out already sent articles
        logger.info("3. Filtering unsent articles...")
        unsent_articles = db.filter_unsent_articles(articles)
        logger.info(
            f"Found {len(unsent_articles)} new articles (total: {len(articles)})"
        )

        if not unsent_articles:
            logger.info("All articles were already sent.")
            telegram.send_message("✅ Все новости уже были отправлены ранее.")
            return

        # Create digest with AI
        logger.info("4. Creating digest with Claude AI...")
        digest = ai_processor.create_digest(unsent_articles, max_articles=20)

        # Send to Telegram
        logger.info("5. Sending to Telegram...")
        success = telegram.send_message(digest)

        if success:
            # Mark articles as sent
            logger.info("6. Marking articles as sent...")
            for article in unsent_articles:
                db.mark_article_sent(article["link"], article["title"])

            logger.info("Digest sent successfully!")
        else:
            logger.error("Failed to send digest")

        # Cleanup old records
        logger.info("7. Cleaning up old database records...")
        db.cleanup_old_records(days=30)

        # Show stats
        stats = db.get_stats()
        logger.info(f"Database stats: {stats['total_articles']} articles tracked")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Validate configuration using Pydantic
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
    logger.info("Configuration validated successfully")

    # Run digest
    send_digest()


if __name__ == "__main__":
    main()
