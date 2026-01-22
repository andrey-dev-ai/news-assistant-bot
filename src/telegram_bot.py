"""Telegram bot for sending news digests."""

import asyncio
import json
import os
from typing import List, Optional

import requests
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import RequestException, Timeout
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from logger import get_logger

logger = get_logger("news_bot.telegram")


class TelegramSender:
    """Send messages via Telegram bot using direct HTTP API."""

    def __init__(
        self,
        bot_token: str = None,
        user_id: str = None,
        channel_id: str = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.user_id = user_id or os.getenv("TELEGRAM_USER_ID")
        self.channel_id = channel_id or os.getenv("TELEGRAM_CHANNEL_ID")

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found")
        if not self.user_id:
            raise ValueError("TELEGRAM_USER_ID not found")

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RequestException, Timeout, ReqConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Telegram API retry {retry_state.attempt_number}: "
            f"{retry_state.outcome.exception()}"
        ),
    )
    def _make_request(
        self, endpoint: str, data: dict, timeout: int = 30
    ) -> dict:
        """
        Make HTTP request to Telegram API with retry.

        Args:
            endpoint: API endpoint (e.g., 'sendMessage')
            data: Request data
            timeout: Request timeout in seconds

        Returns:
            API response as dict
        """
        url = f"{self.api_url}/{endpoint}"
        response = requests.post(url, data=data, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise Exception(f"Telegram API error: {result}")
        return result

    def _send_to_chat(
        self, chat_id: str, text: str, parse_mode: str = "Markdown"
    ) -> None:
        """Send message to any chat (user or channel)."""
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        self._make_request("sendMessage", data)

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send message to user via HTTP API."""
        try:
            if len(text) > 4000:
                chunks = self._split_message(text, max_length=4000)
                for chunk in chunks:
                    self._send_to_chat(self.user_id, chunk, parse_mode)
            else:
                self._send_to_chat(self.user_id, text, parse_mode)

            logger.info(f"Message sent to user {self.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_to_channel(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send message to Telegram channel.

        Args:
            text: Message text
            parse_mode: Message parse mode

        Returns:
            True if message was sent successfully
        """
        if not self.channel_id:
            logger.error("TELEGRAM_CHANNEL_ID not configured")
            return False

        try:
            if len(text) > 4000:
                chunks = self._split_message(text, max_length=4000)
                for chunk in chunks:
                    self._send_to_chat(self.channel_id, chunk, parse_mode)
            else:
                self._send_to_chat(self.channel_id, text, parse_mode)

            logger.info(f"Message sent to channel {self.channel_id}")
            return True
        except Exception as e:
            logger.error(f"Error sending to channel: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RequestException, Timeout, ReqConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Telegram API retry {retry_state.attempt_number}: "
            f"{retry_state.outcome.exception()}"
        ),
    )
    def _send_photo(
        self, chat_id: str, photo_path: str, caption: str, parse_mode: str = "Markdown"
    ) -> dict:
        """
        Send photo to a chat using multipart/form-data.

        Args:
            chat_id: Chat ID to send to
            photo_path: Path to local image file
            caption: Photo caption (max 1024 chars)
            parse_mode: Parse mode for caption

        Returns:
            API response as dict
        """
        url = f"{self.api_url}/sendPhoto"

        # Truncate caption if too long (Telegram limit is 1024)
        if len(caption) > 1024:
            caption = caption[:1021] + "..."

        with open(photo_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": parse_mode,
            }
            response = requests.post(url, data=data, files=files, timeout=60)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            return result

    def send_photo_to_channel(
        self, photo_path: str, caption: str, parse_mode: str = "Markdown"
    ) -> bool:
        """
        Send photo with caption to Telegram channel.

        Args:
            photo_path: Path to local image file
            caption: Photo caption
            parse_mode: Parse mode for caption

        Returns:
            True if photo was sent successfully
        """
        if not self.channel_id:
            logger.error("TELEGRAM_CHANNEL_ID not configured")
            return False

        try:
            self._send_photo(self.channel_id, photo_path, caption, parse_mode)
            logger.info(f"Photo sent to channel {self.channel_id}")
            return True
        except FileNotFoundError:
            logger.error(f"Photo file not found: {photo_path}")
            return False
        except Exception as e:
            logger.error(f"Error sending photo to channel: {e}")
            return False

    def send_photo(
        self, photo_path: str, caption: str, parse_mode: str = "Markdown"
    ) -> bool:
        """
        Send photo with caption to user.

        Args:
            photo_path: Path to local image file
            caption: Photo caption
            parse_mode: Parse mode for caption

        Returns:
            True if photo was sent successfully
        """
        try:
            self._send_photo(self.user_id, photo_path, caption, parse_mode)
            logger.info(f"Photo sent to user {self.user_id}")
            return True
        except FileNotFoundError:
            logger.error(f"Photo file not found: {photo_path}")
            return False
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            return False

    def _split_message(self, text: str, max_length: int = 4000) -> List[str]:
        """Split long message into chunks."""
        chunks = []
        current_chunk = ""

        for line in text.split("\n"):
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def send_message_with_button(
        self, text: str, parse_mode: str = "Markdown"
    ) -> bool:
        """Send message with 'Get Digest' button."""
        try:
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📰 Получить дайджест", "callback_data": "get_digest"}]
                ]
            }

            if len(text) > 4000:
                chunks = self._split_message(text, max_length=4000)
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        self._send_with_keyboard(chunk, parse_mode, keyboard)
                    else:
                        self._send_to_chat(self.user_id, chunk, parse_mode)
            else:
                self._send_with_keyboard(text, parse_mode, keyboard)
            return True
        except Exception as e:
            logger.error(f"Error sending message with button: {e}")
            return False

    def _send_with_keyboard(
        self, text: str, parse_mode: str, keyboard: dict
    ) -> None:
        """Send message with keyboard using direct HTTP request."""
        data = {
            "chat_id": self.user_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": json.dumps(keyboard),
        }
        self._make_request("sendMessage", data)


class TelegramBotHandler:
    """Interactive Telegram bot with commands."""

    def __init__(self, digest_callback):
        """
        Initialize bot handler.

        Args:
            digest_callback: Function to call when digest is requested
        """
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.user_id = os.getenv("TELEGRAM_USER_ID")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
        self.digest_callback = digest_callback
        self.app = None

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /start command."""
        keyboard = [
            [InlineKeyboardButton("📰 Получить дайджест", callback_data="get_digest")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 Привет! Я AI News Bot.\n\n"
            "Я собираю новости об искусственном интеллекте и отправляю дайджест.\n\n"
            "📅 Автоматическая отправка: каждый день в 08:00 UTC\n\n"
            "Команды:\n"
            "/digest - получить дайджест сейчас\n"
            "/post - опубликовать в канал\n"
            "/help - помощь",
            reply_markup=reply_markup,
        )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /help command."""
        await update.message.reply_text(
            "🤖 *AI News Bot - Помощь*\n\n"
            "*Phase 2 команды:*\n"
            "/generate - сгенерировать 5 постов на день\n"
            "/preview - посмотреть запланированные посты\n"
            "/publish\\_now - опубликовать следующий пост\n"
            "/stats - статистика и мониторинг\n\n"
            "*Legacy команды:*\n"
            "/digest - получить дайджест лично\n"
            "/post - опубликовать дайджест в канал\n\n"
            "/start - начать работу\n"
            "/help - эта справка",
            parse_mode="Markdown",
        )

    async def digest_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /digest command."""
        await update.message.reply_text("⏳ Собираю новости, подождите...")

        try:
            await asyncio.to_thread(self.digest_callback)
        except Exception as e:
            logger.error(f"Error in /digest command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def generate_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /generate command - generate 5 posts for today."""
        # Check if user is authorized
        if str(update.effective_user.id) != self.user_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return

        await update.message.reply_text("⏳ Генерирую 5 постов на сегодня...")

        try:
            from database import Database
            from post_generator import PostGenerator
            from post_queue import PostQueue
            from rss_parser import RSSParser

            parser = RSSParser()
            db = Database()
            generator = PostGenerator()
            queue = PostQueue()

            # Fetch and filter articles
            articles = parser.fetch_recent_news(hours=24)
            if not articles:
                await update.message.reply_text("❌ Нет статей для обработки.")
                return

            unsent = db.filter_unsent_articles(articles)
            if not unsent:
                await update.message.reply_text("❌ Нет новых статей.")
                return

            await update.message.reply_text(
                f"📰 Найдено {len(unsent)} новых статей. Генерирую посты..."
            )

            # Generate posts
            posts = generator.generate_daily_posts(unsent, count=5)
            if not posts:
                await update.message.reply_text("❌ Не удалось сгенерировать посты.")
                return

            # Schedule posts
            times = ["09:00", "12:00", "15:00", "18:00", "21:00"]
            post_dicts = [
                {
                    "text": post.text,
                    "article_url": post.article_url,
                    "article_title": post.article_title,
                    "image_prompt": post.image_prompt,
                    "format": post.format.value,
                }
                for post in posts
            ]
            post_ids = queue.schedule_posts_for_day(post_dicts, times=times)

            # Mark articles as sent
            for post in posts:
                db.mark_article_sent(post.article_url, post.article_title)

            # Show preview
            stats = queue.get_stats()
            await update.message.reply_text(
                f"✅ Сгенерировано {len(posts)} постов!\n\n"
                f"📅 Расписание: {', '.join(times[:len(posts)])}\n"
                f"📊 В очереди: {stats.get('pending', 0)} постов\n\n"
                f"Используйте /preview чтобы посмотреть посты."
            )

        except Exception as e:
            logger.error(f"Error in /generate command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def preview_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /preview command - show today's scheduled posts."""
        try:
            from post_queue import PostQueue

            queue = PostQueue()
            posts = queue.get_all_pending(limit=10)

            if not posts:
                await update.message.reply_text("📭 Нет запланированных постов.")
                return

            await update.message.reply_text(f"📋 *Запланировано постов:* {len(posts)}\n", parse_mode="Markdown")

            for i, post in enumerate(posts, 1):
                status_emoji = {
                    "pending": "⏳",
                    "published": "✅",
                    "failed": "❌",
                }.get(post["status"], "❓")

                scheduled = post.get("scheduled_at", "")[:16] if post.get("scheduled_at") else "—"

                # Full preview without markdown parsing
                format_type = post.get('format', 'unknown')
                preview = f"{status_emoji} Пост {i} ({format_type})\n⏰ {scheduled}\n\n"
                preview += post["post_text"][:500]
                if len(post["post_text"]) > 500:
                    preview += "..."
                await update.message.reply_text(preview)

        except Exception as e:
            logger.error(f"Error in /preview command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def publish_now_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /publish_now command - publish next pending post immediately."""
        if str(update.effective_user.id) != self.user_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return

        try:
            from post_queue import PostQueue

            queue = PostQueue()
            post = queue.get_next_pending()

            if not post:
                await update.message.reply_text("📭 Нет постов для публикации.")
                return

            await update.message.reply_text(f"⏳ Публикую пост {post['id']}...")

            # Generate image if needed
            image_path = post.get("image_url")
            if not image_path and post.get("image_prompt"):
                try:
                    from image_generator import get_image_generator

                    await update.message.reply_text("🎨 Генерирую картинку...")
                    generator = get_image_generator()
                    image_path = generator.generate_for_post(
                        post_id=post["id"],
                        image_prompt=post["image_prompt"],
                        category=post.get("format"),
                    )
                    if image_path:
                        queue.update_image_url(post["id"], image_path)
                except Exception as e:
                    logger.warning(f"Failed to generate image: {e}")
                    await update.message.reply_text(f"⚠️ Картинка не сгенерирована: {e}")

            sender = TelegramSender()

            # Send with image if available
            if image_path:
                success = sender.send_photo_to_channel(image_path, post["post_text"])
            else:
                success = sender.send_to_channel(post["post_text"])

            if success:
                queue.mark_published(post["id"])
                await update.message.reply_text(
                    f"✅ Пост {post['id']} опубликован в канал!"
                )
            else:
                queue.mark_failed(post["id"], "Manual publish failed")
                await update.message.reply_text("❌ Ошибка при публикации.")

        except Exception as e:
            logger.error(f"Error in /publish_now command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def stats_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /stats command - show bot statistics and monitoring."""
        if str(update.effective_user.id) != self.user_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return

        try:
            from monitoring import get_monitor

            monitor = get_monitor()
            stats_msg = monitor.format_stats_message()

            await update.message.reply_text(stats_msg, parse_mode="Markdown")

            # If there are alerts, also send daily report
            alerts = monitor.get_alerts()
            if alerts:
                report = monitor.format_daily_report()
                await update.message.reply_text(report, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in /stats command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def post_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /post command - publish digest to channel (legacy)."""
        # Check if user is authorized
        if str(update.effective_user.id) != self.user_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return

        # Check if channel is configured
        if not self.channel_id:
            await update.message.reply_text(
                "❌ Канал не настроен.\n"
                "Добавьте TELEGRAM_CHANNEL_ID в .env файл."
            )
            return

        await update.message.reply_text("⏳ Создаю дайджест для публикации в канал...")

        try:
            # Import here to avoid circular imports
            from ai_processor import AIProcessor
            from database import Database
            from rss_parser import RSSParser

            parser = RSSParser()
            ai_processor = AIProcessor()
            db = Database()

            # Fetch and filter articles
            articles = parser.fetch_recent_news(hours=24)
            if not articles:
                await update.message.reply_text("❌ Нет статей для публикации.")
                return

            unsent = db.filter_unsent_articles(articles)
            if not unsent:
                await update.message.reply_text("❌ Нет новых статей для публикации.")
                return

            # Create digest
            digest = ai_processor.create_digest(unsent)

            # Send to channel
            sender = TelegramSender()
            success = sender.send_to_channel(digest)

            if success:
                # Mark articles as sent
                for article in unsent[:20]:  # Same limit as digest
                    db.mark_article_sent(article["link"], article["title"])
                await update.message.reply_text("✅ Дайджест опубликован в канал!")
            else:
                await update.message.reply_text("❌ Ошибка при публикации в канал.")

        except Exception as e:
            logger.error(f"Error in /post command: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def button_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle button press."""
        query = update.callback_query
        await query.answer()

        if query.data == "get_digest":
            await query.message.reply_text("⏳ Собираю новости, подождите...")

            try:
                await asyncio.to_thread(self.digest_callback)
            except Exception as e:
                logger.error(f"Error in button callback: {e}")
                await query.message.reply_text(f"❌ Ошибка: {e}")

    def run(self):
        """Run the bot."""
        self.app = Application.builder().token(self.bot_token).build()

        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("digest", self.digest_command))
        self.app.add_handler(CommandHandler("post", self.post_command))
        self.app.add_handler(CommandHandler("generate", self.generate_command))
        self.app.add_handler(CommandHandler("preview", self.preview_command))
        self.app.add_handler(CommandHandler("publish_now", self.publish_now_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

        logger.info("Bot started. Waiting for commands...")
        self.app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    sender = TelegramSender()

    test_message = """🤖 *Тестовое сообщение*

Это тест вашего AI News Bot!
Бот работает корректно!"""

    print("Sending test message with button...")
    sender.send_message_with_button(test_message)
