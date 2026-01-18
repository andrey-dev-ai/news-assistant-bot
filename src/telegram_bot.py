"""Telegram bot for sending news digests."""

import os
import asyncio
import requests
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError


class TelegramSender:
    """Send messages via Telegram bot using direct HTTP API."""

    def __init__(self, bot_token: str = None, user_id: str = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.user_id = user_id or os.getenv('TELEGRAM_USER_ID')

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found")
        if not self.user_id:
            raise ValueError("TELEGRAM_USER_ID not found")

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Send message to user via HTTP API."""
        try:
            if len(text) > 4000:
                chunks = self._split_message(text, max_length=4000)
                for chunk in chunks:
                    self._send_via_http(chunk, parse_mode)
            else:
                self._send_via_http(text, parse_mode)

            print(f"Message sent successfully to {self.user_id}")
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def _send_via_http(self, text: str, parse_mode: str = 'Markdown'):
        """Send message using direct HTTP request."""
        url = f"{self.api_url}/sendMessage"
        data = {
            'chat_id': self.user_id,
            'text': text,
            'parse_mode': parse_mode
        }
        response = requests.post(url, data=data)
        if not response.ok:
            raise Exception(f"Telegram API error: {response.text}")

    def _split_message(self, text: str, max_length: int = 4000) -> list:
        """Split long message into chunks."""
        chunks = []
        current_chunk = ""

        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += '\n' + line if current_chunk else line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def send_message_with_button(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Send message with 'Get Digest' button."""
        try:
            import json
            keyboard = {"inline_keyboard": [[{"text": "📰 Получить дайджест", "callback_data": "get_digest"}]]}

            if len(text) > 4000:
                chunks = self._split_message(text, max_length=4000)
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:
                        self._send_via_http_with_keyboard(chunk, parse_mode, keyboard)
                    else:
                        self._send_via_http(chunk, parse_mode)
            else:
                self._send_via_http_with_keyboard(text, parse_mode, keyboard)
            return True
        except Exception as e:
            print(f"Error sending message with button: {e}")
            return False

    def _send_via_http_with_keyboard(self, text: str, parse_mode: str, keyboard: dict):
        """Send message with keyboard using direct HTTP request."""
        import json
        url = f"{self.api_url}/sendMessage"
        data = {
            'chat_id': self.user_id,
            'text': text,
            'parse_mode': parse_mode,
            'reply_markup': json.dumps(keyboard)
        }
        response = requests.post(url, data=data)
        if not response.ok:
            raise Exception(f"Telegram API error: {response.text}")


class TelegramBotHandler:
    """Interactive Telegram bot with commands."""

    def __init__(self, digest_callback):
        """
        Initialize bot handler.

        Args:
            digest_callback: Function to call when digest is requested
        """
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.user_id = os.getenv('TELEGRAM_USER_ID')
        self.digest_callback = digest_callback
        self.app = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        keyboard = [[InlineKeyboardButton("📰 Получить дайджест", callback_data='get_digest')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "👋 Привет! Я AI News Bot.\n\n"
            "Я собираю новости об искусственном интеллекте и отправляю дайджест.\n\n"
            "📅 Автоматическая отправка: каждый день в 08:00 UTC\n\n"
            "Команды:\n"
            "/digest - получить дайджест сейчас\n"
            "/help - помощь",
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await update.message.reply_text(
            "🤖 *AI News Bot - Помощь*\n\n"
            "*Команды:*\n"
            "/start - начать работу с ботом\n"
            "/digest - получить дайджест сейчас\n"
            "/help - эта справка\n\n"
            "*Что делает бот:*\n"
            "• Собирает новости из 6 источников об AI\n"
            "• Анализирует через Claude AI\n"
            "• Переводит на русский\n"
            "• Отправляет 8-12 лучших новостей",
            parse_mode='Markdown'
        )

    async def digest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /digest command."""
        await update.message.reply_text("⏳ Собираю новости, подождите...")

        try:
            await asyncio.to_thread(self.digest_callback)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button press."""
        query = update.callback_query
        await query.answer()

        if query.data == 'get_digest':
            await query.message.reply_text("⏳ Собираю новости, подождите...")

            try:
                await asyncio.to_thread(self.digest_callback)
            except Exception as e:
                await query.message.reply_text(f"❌ Ошибка: {e}")

    def run(self):
        """Run the bot."""
        self.app = Application.builder().token(self.bot_token).build()

        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("digest", self.digest_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))

        print("🤖 Bot started. Waiting for commands...")
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
