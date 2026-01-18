"""Scheduler for running bot at specified times with interactive commands."""

import schedule
import time
import os
import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import send_digest
from telegram_bot import TelegramBotHandler


def scheduled_job():
    """Job to run on schedule."""
    print("\n" + "=" * 50)
    print("Scheduled job started")
    print("=" * 50)
    send_digest()


def run_scheduler():
    """Run the scheduler in background."""
    load_dotenv()

    times_str = os.getenv('DIGEST_TIMES', '08:00')
    times = [t.strip() for t in times_str.split(',')]

    print(f"📅 Scheduled times: {', '.join(times)}")

    for time_str in times:
        schedule.every().day.at(time_str).do(scheduled_job)
        print(f"✓ Scheduled daily digest at {time_str}")

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    """Main entry point with interactive bot."""
    load_dotenv()

    print("=" * 50)
    print("AI News Bot Started")
    print("=" * 50)

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Run interactive bot in main thread
    bot = TelegramBotHandler(digest_callback=send_digest)
    bot.run()


if __name__ == "__main__":
    main()
