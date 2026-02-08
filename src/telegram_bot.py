"""Telegram bot for sending news digests."""

import asyncio
import json
import os
import re
from typing import List, Optional

import requests


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text for safe preview truncation."""
    return re.sub(r'<[^>]+>', '', text)
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import RequestException, Timeout
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
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
        self, chat_id: str, text: str, parse_mode: str = "HTML", disable_preview: bool = True
    ) -> dict:
        """Send message to any chat (user or channel)."""
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        return self._make_request("sendMessage", data)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
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

    def send_to_channel(
        self, text: str, parse_mode: str = "HTML", article_url: str = None
    ) -> Optional[int]:
        """
        Send message to Telegram channel.

        Args:
            text: Message text
            parse_mode: Message parse mode
            article_url: Optional URL for "Читати далі" button

        Returns:
            Message ID if sent successfully, None otherwise
        """
        if not self.channel_id:
            logger.error("TELEGRAM_CHANNEL_ID not configured")
            return None

        try:
            reply_markup = None
            if article_url:
                import json as _json
                reply_markup = _json.dumps({
                    "inline_keyboard": [[{"text": "Читати далі →", "url": article_url}]]
                })

            if len(text) > 4000:
                chunks = self._split_message(text, max_length=4000)
                result = None
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1 and reply_markup:
                        data = {
                            "chat_id": self.channel_id,
                            "text": chunk,
                            "parse_mode": parse_mode,
                            "disable_web_page_preview": True,
                            "reply_markup": reply_markup,
                        }
                        result = self._make_request("sendMessage", data)
                    else:
                        result = self._send_to_chat(self.channel_id, chunk, parse_mode)
                message_id = result.get("result", {}).get("message_id") if result else None
            else:
                if reply_markup:
                    data = {
                        "chat_id": self.channel_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                        "reply_markup": reply_markup,
                    }
                    result = self._make_request("sendMessage", data)
                else:
                    result = self._send_to_chat(self.channel_id, text, parse_mode)
                message_id = result.get("result", {}).get("message_id")

            logger.info(f"Message sent to channel {self.channel_id}, message_id={message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Error sending to channel: {e}")
            return None

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
        self, chat_id: str, photo_path: str, caption: str,
        parse_mode: str = "HTML", reply_markup: dict = None
    ) -> dict:
        """
        Send photo to a chat using multipart/form-data.

        Args:
            chat_id: Chat ID to send to
            photo_path: Path to local image file
            caption: Photo caption (max 1024 chars)
            parse_mode: Parse mode for caption
            reply_markup: Optional inline keyboard dict

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
            if reply_markup:
                import json as _json
                data["reply_markup"] = _json.dumps(reply_markup)
            response = requests.post(url, data=data, files=files, timeout=60)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            return result

    def send_photo_to_channel(
        self, photo_path: str, caption: str, parse_mode: str = "HTML",
        article_url: str = None
    ) -> Optional[int]:
        """
        Send photo with caption to Telegram channel.

        Args:
            photo_path: Path to local image file
            caption: Photo caption
            parse_mode: Parse mode for caption
            article_url: Optional URL for "Читати далі" button

        Returns:
            Message ID if sent successfully, None otherwise
        """
        if not self.channel_id:
            logger.error("TELEGRAM_CHANNEL_ID not configured")
            return None

        reply_markup = None
        if article_url:
            reply_markup = {
                "inline_keyboard": [[{"text": "Читати далі →", "url": article_url}]]
            }

        try:
            result = self._send_photo(
                self.channel_id, photo_path, caption, parse_mode, reply_markup
            )
            message_id = result.get("result", {}).get("message_id")
            logger.info(f"Photo sent to channel {self.channel_id}, message_id={message_id}")
            return message_id
        except FileNotFoundError:
            logger.error(f"Photo file not found: {photo_path}")
            return None
        except Exception as e:
            logger.error(f"Error sending photo to channel: {e}")
            return None

    def send_photo(
        self, photo_path: str, caption: str, parse_mode: str = "HTML"
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
        self, text: str, parse_mode: str = "HTML"
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

    def _get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Get the persistent reply keyboard for the bot."""
        keyboard = [
            [KeyboardButton("📋 Очередь"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("🔄 Обновить"), KeyboardButton("⚙️ Настройки")],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            is_persistent=True,
        )

    def _get_moderation_keyboard(self, post_id: int) -> InlineKeyboardMarkup:
        """Get inline keyboard for post moderation."""
        keyboard = [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve_{post_id}"),
                InlineKeyboardButton("📅 Отложить", callback_data=f"schedule_{post_id}"),
            ],
            [
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{post_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{post_id}"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /start command."""
        await update.message.reply_text(
            "👋 KLYMO AI Bot — автоматизация для бизнеса.\n\n"
            "Генерирую 1 пост/день с бизнес-фокусом.\n"
            "Каждый пост проходит модерацию.\n\n"
            "📋 <b>Очередь</b> — посты на модерацию\n"
            "📊 <b>Статистика</b> — метрики канала\n"
            "🔄 <b>Обновить</b> — сгенерировать пост\n"
            "⚙️ <b>Настройки</b> — конфигурация\n\n"
            "/help — справка",
            parse_mode="HTML",
            reply_markup=self._get_main_keyboard(),
        )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /help command."""
        await update.message.reply_text(
            "🤖 <b>KLYMO AI Bot — Помощь</b>\n\n"
            "<b>Режим:</b> 1 пост/день, бизнес-фокус, лидген → @klymo_tech\n\n"
            "<b>Кнопки:</b>\n"
            "📋 Очередь — посты ожидающие одобрения\n"
            "📊 Статистика — метрики канала\n"
            "🔄 Обновить — сгенерировать пост\n"
            "⚙️ Настройки — конфигурация бота\n\n"
            "<b>Команды:</b>\n"
            "/generate - сгенерировать пост\n"
            "/preview - посмотреть очередь\n"
            "/publish_now - опубликовать следующий пост\n"
            "/stats - статистика\n\n"
            "/start - начать работу\n"
            "/help - эта справка",
            parse_mode="HTML",
            reply_markup=self._get_main_keyboard(),
        )

    async def handle_keyboard_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle persistent keyboard button presses."""
        text = update.message.text

        if text == "📋 Очередь":
            await self._show_moderation_queue(update, context)
        elif text == "📊 Статистика":
            await self.stats_command(update, context)
        elif text == "🔄 Обновить":
            await self.generate_command(update, context)
        elif text == "⚙️ Настройки":
            await self._show_settings(update, context)
        else:
            # Unknown button, ignore
            pass

    async def _show_moderation_queue(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show posts waiting for moderation."""
        try:
            from moderation import get_moderation_queue

            mq = get_moderation_queue()
            posts = mq.get_pending_posts(limit=10)

            if not posts:
                await update.message.reply_text(
                    "📭 Нет постов ожидающих одобрения.\n\n"
                    "Нажмите 🔄 Обновить чтобы сгенерировать новые.",
                    reply_markup=self._get_main_keyboard(),
                )
                return

            await update.message.reply_text(
                f"📋 <b>Посты на модерацию:</b> {len(posts)}\n",
                parse_mode="HTML",
            )

            for post in posts:
                # Send each post with moderation buttons
                # Strip HTML tags to avoid unclosed tag errors when truncating
                clean_text = strip_html_tags(post["post_text"])
                post_preview = clean_text[:800]
                if len(clean_text) > 800:
                    post_preview += "..."

                rubric = post.get("rubric") or post.get("format", "unknown")
                image_url = post.get("image_url")

                # Информация об изображении
                if image_url:
                    if image_url.startswith(("http://", "https://")):
                        image_info = "🖼 Изображение: OG из источника"
                    else:
                        image_info = "🖼 Изображение: локальный файл"
                elif post.get("image_prompt"):
                    image_info = "🎨 Изображение: будет сгенерировано"
                else:
                    image_info = "⚠️ Без изображения"

                # Если есть локальный файл изображения — отправляем как фото
                if image_url and not image_url.startswith(("http://", "https://")):
                    try:
                        caption = f"<b>#{post['id']}</b> | {rubric}\n\n{post_preview[:900]}"
                        await update.message.reply_photo(
                            photo=open(image_url, "rb"),
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=self._get_moderation_keyboard(post["id"]),
                        )
                        continue
                    except Exception as e:
                        logger.warning(f"Failed to send photo preview: {e}")

                # Иначе отправляем текст с информацией об изображении
                await update.message.reply_text(
                    f"<b>#{post['id']}</b> | {rubric}\n"
                    f"{image_info}\n\n"
                    f"{post_preview}",
                    parse_mode="HTML",
                    reply_markup=self._get_moderation_keyboard(post["id"]),
                    disable_web_page_preview=True,
                )

        except Exception as e:
            logger.error(f"Error showing moderation queue: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def _show_settings(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show bot settings."""
        try:
            from config import get_settings

            settings = get_settings()

            await update.message.reply_text(
                "⚙️ <b>Настройки бота</b>\n\n"
                f"<b>Модерация:</b> {'✅ Включена' if settings.use_moderation else '❌ Выключена'}\n"
                f"<b>Рубрики:</b> {'✅ Включены' if settings.use_rubrics else '❌ Выключены'}\n"
                f"<b>Новое расписание:</b> {'✅ Включено' if settings.use_new_schedule else '❌ Выключено'}\n\n"
                f"<b>Канал:</b> {self.channel_id or 'Не настроен'}\n"
                f"<b>RSS источников:</b> 15",
                parse_mode="HTML",
                reply_markup=self._get_main_keyboard(),
            )
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

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
        """Handle /generate command - generate posts and send for moderation."""
        # Check if user is authorized
        if str(update.effective_user.id) != self.user_id:
            await update.message.reply_text("❌ У вас нет прав для этой команды.")
            return

        await update.message.reply_text(
            "⏳ Генерирую посты...",
            reply_markup=self._get_main_keyboard(),
        )

        try:
            from config import get_settings
            from database import Database
            from moderation import get_moderation_queue
            from post_generator import PostGenerator
            from post_queue import PostQueue
            from rss_parser import RSSParser

            settings = get_settings()
            parser = RSSParser()
            db = Database()
            generator = PostGenerator()
            queue = PostQueue()
            mq = get_moderation_queue()

            # Fetch and filter articles
            articles = parser.fetch_recent_news(hours=24)
            if not articles:
                await update.message.reply_text("❌ Нет статей для обработки.")
                return

            unsent = db.filter_unsent_articles(articles)
            if not unsent:
                await update.message.reply_text("❌ Нет новых статей.")
                return

            # Enrich articles with OG images (for those without RSS images)
            await update.message.reply_text(
                f"📰 Найдено {len(unsent)} новых статей. Загружаю картинки..."
            )
            unsent = parser.enrich_with_og_images(unsent[:25])  # Increased limit for better coverage

            await update.message.reply_text("🎨 Генерирую посты...")

            # Generate posts (1 per day — KLYMO Business Pivot)
            posts = generator.generate_daily_posts(unsent, count=1)
            if not posts:
                await update.message.reply_text("❌ Не удалось сгенерировать посты.")
                return

            # Add posts to queue
            post_dicts = [
                {
                    "text": post.text,
                    "article_url": post.article_url,
                    "article_title": post.article_title,
                    "image_url": post.image_url,
                    "image_prompt": post.image_prompt,
                    "format": post.format.value,
                }
                for post in posts
            ]

            # If moderation is enabled, send for approval instead of scheduling
            if settings.use_moderation:
                post_ids = []
                for post_dict in post_dicts:
                    post_id = queue.add_post(
                        post_text=post_dict["text"],
                        article_url=post_dict["article_url"],
                        article_title=post_dict["article_title"],
                        image_url=post_dict.get("image_url"),
                        image_prompt=post_dict.get("image_prompt"),
                        format_type=post_dict["format"],
                    )
                    # Mark as pending approval
                    mq.send_for_approval(post_id)
                    post_ids.append(post_id)

                # Mark articles as sent
                for post in posts:
                    db.mark_article_sent(post.article_url, post.article_title)

                await update.message.reply_text(
                    f"✅ Сгенерировано {len(posts)} постов!\n\n"
                    f"📋 Посты отправлены на модерацию.\n"
                    f"Нажмите <b>📋 Очередь</b> чтобы одобрить.",
                    parse_mode="HTML",
                    reply_markup=self._get_main_keyboard(),
                )

                # Show first post for quick moderation
                if post_ids:
                    first_post = queue.get_post_by_id(post_ids[0]) if hasattr(queue, 'get_post_by_id') else None
                    if first_post is None:
                        # Fallback: get from moderation queue
                        first_post = mq.get_post_by_id(post_ids[0])

                    if first_post:
                        # Strip HTML tags to avoid unclosed tag errors when truncating
                        clean_text = strip_html_tags(first_post["post_text"])
                        post_preview = clean_text[:800]
                        if len(clean_text) > 800:
                            post_preview += "..."

                        await update.message.reply_text(
                            f"<b>Первый пост #{first_post['id']}</b>\n\n"
                            f"{post_preview}",
                            parse_mode="HTML",
                            reply_markup=self._get_moderation_keyboard(first_post["id"]),
                            disable_web_page_preview=True,
                        )
            else:
                # Legacy mode: schedule posts for auto-publishing
                times = ["10:00"]
                post_ids = queue.schedule_posts_for_day(post_dicts, times=times)

                for post in posts:
                    db.mark_article_sent(post.article_url, post.article_title)

                stats = queue.get_stats()
                await update.message.reply_text(
                    f"✅ Сгенерировано {len(posts)} постов!\n\n"
                    f"📅 Расписание: {', '.join(times[:len(posts)])}\n"
                    f"📊 В очереди: {stats.get('pending', 0)} постов\n\n"
                    f"Используйте /preview чтобы посмотреть посты.",
                    reply_markup=self._get_main_keyboard(),
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

            await update.message.reply_text(f"📋 <b>Запланировано постов:</b> {len(posts)}\n", parse_mode="HTML")

            for i, post in enumerate(posts, 1):
                status_emoji = {
                    "pending": "⏳",
                    "published": "✅",
                    "failed": "❌",
                }.get(post["status"], "❓")

                scheduled = post.get("scheduled_at", "")[:16] if post.get("scheduled_at") else "—"

                # Preview with HTML parsing for proper formatting
                format_type = post.get('format', 'unknown')
                preview = f"{status_emoji} Пост {i} ({format_type})\n⏰ {scheduled}\n\n"
                preview += post["post_text"]
                await update.message.reply_text(preview, parse_mode="HTML", disable_web_page_preview=True)

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

            # Get or download image
            image_path = None
            image_url = post.get("image_url")

            # Step 1: If we have OG/RSS image URL - download it
            if image_url and image_url.startswith(("http://", "https://")):
                try:
                    from og_parser import download_image
                    await update.message.reply_text("📷 Скачиваю картинку...")
                    image_path = download_image(image_url)
                    if image_path:
                        queue.update_image_url(post["id"], image_path)
                        logger.info(f"Downloaded OG image: {image_path}")
                except Exception as e:
                    logger.warning(f"Failed to download OG image: {e}")

            # Step 2: If still no image but have prompt - generate via AI
            if not image_path and post.get("image_prompt"):
                try:
                    from image_generator import get_image_generator

                    await update.message.reply_text("🎨 Генерирую картинку через AI...")
                    generator = get_image_generator()
                    image_path = generator.generate_for_post(
                        post_id=post["id"],
                        image_prompt=post["image_prompt"],
                        category=post.get("format"),
                    )
                    if image_path:
                        queue.update_image_url(post["id"], image_path)
                except Exception as e:
                    logger.warning(f"Failed to generate AI image: {e}")
                    await update.message.reply_text(f"⚠️ Картинка не сгенерирована: {e}")

            sender = TelegramSender()
            article_url = post.get("article_url", "")

            # Send with image if available (HTML for proper formatting)
            if image_path:
                success = sender.send_photo_to_channel(
                    image_path, post["post_text"], parse_mode="HTML",
                    article_url=article_url or None
                )
            else:
                success = sender.send_to_channel(
                    post["post_text"], parse_mode="HTML",
                    article_url=article_url or None
                )

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
            # Show analytics first
            try:
                from analytics import Analytics
                analytics = Analytics()
                analytics_msg = analytics.format_stats_message(days=7)
                await update.message.reply_text(analytics_msg, parse_mode="HTML")

                # Show A/B comparison
                ab_msg = analytics.format_ab_comparison_message(days=30)
                await update.message.reply_text(ab_msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Analytics not available: {e}")

            # Then show monitoring stats
            from monitoring import get_monitor

            monitor = get_monitor()
            stats_msg = monitor.format_stats_message()

            await update.message.reply_text(stats_msg, parse_mode="HTML")

            # If there are alerts, also send daily report
            alerts = monitor.get_alerts()
            if alerts:
                report = monitor.format_daily_report()
                await update.message.reply_text(report, parse_mode="HTML")

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
        """Handle inline button press."""
        query = update.callback_query
        await query.answer()

        data = query.data

        # Legacy: get_digest button
        if data == "get_digest":
            await query.message.reply_text("⏳ Собираю новости, подождите...")
            try:
                await asyncio.to_thread(self.digest_callback)
            except Exception as e:
                logger.error(f"Error in button callback: {e}")
                await query.message.reply_text(f"❌ Ошибка: {e}")
            return

        # Moderation buttons
        if data.startswith("approve_"):
            await self._handle_approve(query, data)
        elif data.startswith("schedule_"):
            await self._handle_schedule(query, data)
        elif data.startswith("edit_"):
            await self._handle_edit(query, data)
        elif data.startswith("reject_"):
            await self._handle_reject(query, data)
        elif data.startswith("confirm_reject_"):
            await self._handle_confirm_reject(query, data)
        elif data.startswith("schedule_time_"):
            await self._handle_schedule_time(query, data)

    async def _handle_approve(self, query, data: str):
        """Approve and immediately publish a post."""
        try:
            post_id = int(data.split("_")[1])

            from moderation import get_moderation_queue

            mq = get_moderation_queue()
            post = mq.get_post_by_id(post_id)

            if not post:
                await query.edit_message_text("❌ Пост не найден.")
                return

            # Approve the post
            mq.approve_post(post_id, approved_by=str(query.from_user.id))

            # Publish immediately
            await query.edit_message_text("⏳ Публикую...")

            # Умный выбор изображения
            image_path = None
            image_url = post.get("image_url")

            # Если уже локальный путь — используем
            if image_url and not image_url.startswith(("http://", "https://")):
                image_path = image_url
            else:
                # Используем умную стратегию выбора
                try:
                    from image_generator import get_image_generator

                    img_generator = get_image_generator()
                    image_path, source = img_generator.choose_image_strategy(
                        og_image_url=image_url,
                        image_prompt=post.get("image_prompt"),
                        category=post.get("format"),
                        post_id=post_id
                    )
                    if image_path:
                        logger.info(f"Image for post {post_id}: {source}")
                except Exception as e:
                    logger.warning(f"Failed to prepare image: {e}")

            # Send to channel
            sender = TelegramSender()
            article_url = post.get("article_url", "")
            if image_path:
                message_id = sender.send_photo_to_channel(
                    image_path, post["post_text"], parse_mode="HTML",
                    article_url=article_url or None
                )
            else:
                message_id = sender.send_to_channel(
                    post["post_text"], parse_mode="HTML",
                    article_url=article_url or None
                )

            if message_id:
                mq.mark_published(post_id)
                # Record in analytics
                try:
                    from analytics import Analytics
                    analytics = Analytics()
                    analytics.record_publication(
                        post_id=post_id,
                        message_id=message_id,
                        channel_id=sender.channel_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to record analytics: {e}")
                await query.edit_message_text(
                    f"✅ Пост #{post_id} опубликован в канал!"
                )
            else:
                mq.mark_failed(post_id, "Failed to send to channel")
                await query.edit_message_text(f"❌ Ошибка публикации поста #{post_id}")

        except Exception as e:
            logger.error(f"Error approving post: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")

    async def _handle_schedule(self, query, data: str):
        """Show scheduling options for a post."""
        post_id = int(data.split("_")[1])

        keyboard = [
            [
                InlineKeyboardButton("🕐 Через 1 час", callback_data=f"schedule_time_{post_id}_1"),
                InlineKeyboardButton("🕑 Через 3 часа", callback_data=f"schedule_time_{post_id}_3"),
            ],
            [
                InlineKeyboardButton("🕕 Через 6 часов", callback_data=f"schedule_time_{post_id}_6"),
                InlineKeyboardButton("📅 Завтра 10:00", callback_data=f"schedule_time_{post_id}_next"),
            ],
            [
                InlineKeyboardButton("◀️ Назад", callback_data=f"back_to_moderation_{post_id}"),
            ],
        ]

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _handle_schedule_time(self, query, data: str):
        """Schedule post for selected time."""
        try:
            parts = data.split("_")
            post_id = int(parts[2])
            time_option = parts[3]

            from datetime import datetime, timedelta
            from moderation import get_moderation_queue

            mq = get_moderation_queue()

            # Calculate scheduled time
            now = datetime.now()
            if time_option == "next":
                # Tomorrow at 10:00
                scheduled = now.replace(hour=10, minute=0, second=0, microsecond=0)
                scheduled += timedelta(days=1)
            else:
                hours = int(time_option)
                scheduled = now + timedelta(hours=hours)

            mq.schedule_post(post_id, scheduled, approved_by=str(query.from_user.id))

            await query.edit_message_text(
                f"📅 Пост #{post_id} запланирован на {scheduled.strftime('%d.%m %H:%M')}"
            )

        except Exception as e:
            logger.error(f"Error scheduling post: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")

    async def _handle_edit(self, query, data: str):
        """Start post editing flow."""
        post_id = int(data.split("_")[1])

        # Store post_id in user_data for later use
        # For now, just show instructions
        await query.answer(
            "Редактирование: скопируйте текст, отредактируйте и отправьте с командой /edit " + str(post_id),
            show_alert=True
        )

    async def _handle_reject(self, query, data: str):
        """Show rejection confirmation."""
        post_id = int(data.split("_")[1])

        keyboard = [
            [
                InlineKeyboardButton("❌ Да, отклонить", callback_data=f"confirm_reject_{post_id}"),
                InlineKeyboardButton("◀️ Отмена", callback_data=f"back_to_moderation_{post_id}"),
            ],
        ]

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _handle_confirm_reject(self, query, data: str):
        """Confirm post rejection."""
        try:
            post_id = int(data.split("_")[2])

            from moderation import get_moderation_queue

            mq = get_moderation_queue()
            mq.reject_post(post_id, reason="Rejected by owner")

            await query.edit_message_text(f"❌ Пост #{post_id} отклонён.")

        except Exception as e:
            logger.error(f"Error rejecting post: {e}")
            await query.edit_message_text(f"❌ Ошибка: {e}")

    def run(self):
        """Run the bot with Python 3.14+ compatibility."""
        import sys

        self.app = Application.builder().token(self.bot_token).build()

        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("digest", self.digest_command))
        self.app.add_handler(CommandHandler("post", self.post_command))
        self.app.add_handler(CommandHandler("generate", self.generate_command))
        self.app.add_handler(CommandHandler("preview", self.preview_command))
        self.app.add_handler(CommandHandler("publish_now", self.publish_now_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))

        # Keyboard button handler (must be before CallbackQueryHandler)
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r'^(📋 Очередь|📊 Статистика|🔄 Обновить|⚙️ Настройки)$'),
            self.handle_keyboard_button
        ))

        # Inline button callback handler
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

        logger.info("Bot started. Waiting for commands...")

        # Python 3.14+ removed implicit event loop creation
        if sys.version_info >= (3, 14):
            logger.info("Using asyncio.run() for Python 3.14+")
            asyncio.run(self._run_polling_async())
        else:
            self.app.run_polling(drop_pending_updates=True)

    async def _run_polling_async(self):
        """Run polling asynchronously for Python 3.14+ compatibility."""
        async with self.app:
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot polling started")
            try:
                while True:
                    await asyncio.sleep(1)
            except (asyncio.CancelledError, KeyboardInterrupt):
                logger.info("Shutdown signal received")
            finally:
                await self.app.updater.stop()
                await self.app.stop()
                logger.info("Bot stopped")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    sender = TelegramSender()

    test_message = """🤖 <b>Тестовое сообщение</b>

Это тест вашего AI News Bot!
Бот работает корректно!

👉 <a href="https://example.com">Тестовая ссылка</a>"""

    print("Sending test message with button...")
    sender.send_message_with_button(test_message)
