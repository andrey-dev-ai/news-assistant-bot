"""Main script for AI News Assistant Bot."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rss_parser import RSSParser
from ai_processor import AIProcessor
from telegram_bot import TelegramSender
from database import Database


def send_digest():
    """Collect news, process with AI, and send to Telegram."""
    print("=" * 50)
    print("Starting AI News Digest Bot")
    print("=" * 50)

    try:
        # Initialize components
        print("\n1. Initializing components...")
        parser = RSSParser()
        ai_processor = AIProcessor()
        telegram = TelegramSender()
        db = Database()

        # Fetch recent news
        print("\n2. Fetching news from RSS feeds...")
        articles = parser.fetch_recent_news(hours=24)

        if not articles:
            print("No articles found.")
            telegram.send_message("📭 Нет новых статей за последние 24 часа.")
            return

        # Filter out already sent articles
        print("\n3. Filtering unsent articles...")
        unsent_articles = db.filter_unsent_articles(articles)
        print(f"Found {len(unsent_articles)} new articles (total: {len(articles)})")

        if not unsent_articles:
            print("All articles were already sent.")
            telegram.send_message("✅ Все новости уже были отправлены ранее.")
            return

        # Create digest with AI
        print("\n4. Creating digest with Claude AI...")
        digest = ai_processor.create_digest(unsent_articles, max_articles=20)

        # Send to Telegram
        print("\n5. Sending to Telegram...")
        success = telegram.send_message(digest)

        if success:
            # Mark articles as sent
            print("\n6. Marking articles as sent...")
            for article in unsent_articles:
                db.mark_article_sent(article['link'], article['title'])

            print("\n✅ Digest sent successfully!")
        else:
            print("\n❌ Failed to send digest")

        # Cleanup old records
        print("\n7. Cleaning up old database records...")
        db.cleanup_old_records(days=30)

        # Show stats
        stats = db.get_stats()
        print(f"\nDatabase stats: {stats['total_articles']} articles tracked")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Check required environment variables
    required_vars = ['ANTHROPIC_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_USER_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease create a .env file based on .env.example")
        sys.exit(1)

    # Run digest
    send_digest()


if __name__ == "__main__":
    main()
