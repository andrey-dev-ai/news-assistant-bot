"""Тестовый скрипт для проверки пайплайна с картинками."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

load_dotenv()


def test_image_generator():
    """Тест генератора изображений."""
    print("=" * 50)
    print("Тест 1: ImageGenerator")
    print("=" * 50)

    try:
        from image_generator import get_image_generator

        generator = get_image_generator()
        print("✅ ImageGenerator инициализирован")

        # Тестовая генерация
        test_prompt = "Минималистичная иконка AI-ассистента в стиле flat design, пастельные цвета"
        print(f"Генерирую тестовое изображение: {test_prompt[:50]}...")

        path = generator.generate(test_prompt, filename="test_image")
        if path:
            print(f"✅ Изображение сохранено: {path}")
            return path
        else:
            print("❌ Изображение не сгенерировано")
            return None

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


def test_telegram_sender(image_path: str = None):
    """Тест отправки в Telegram."""
    print("\n" + "=" * 50)
    print("Тест 2: TelegramSender")
    print("=" * 50)

    try:
        from telegram_bot import TelegramSender

        sender = TelegramSender()
        print("✅ TelegramSender инициализирован")
        print(f"   User ID: {sender.user_id}")
        print(f"   Channel ID: {sender.channel_id}")

        # Тест отправки текста
        test_text = "🧪 Тестовое сообщение от news-assistant-bot\n\nПроверка пайплайна с картинками."

        print("\nОтправляю текстовое сообщение пользователю...")
        if sender.send_message(test_text):
            print("✅ Текст отправлен пользователю")
        else:
            print("❌ Ошибка отправки текста")

        # Тест отправки фото если есть
        if image_path and Path(image_path).exists():
            print(f"\nОтправляю фото пользователю: {image_path}")
            caption = "🎨 *Тестовое изображение*\n\nСгенерировано GPT Image 1 Mini"
            if sender.send_photo(image_path, caption):
                print("✅ Фото отправлено пользователю")
            else:
                print("❌ Ошибка отправки фото")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_full_pipeline():
    """Полный тест пайплайна: генерация поста -> картинка -> отправка."""
    print("\n" + "=" * 50)
    print("Тест 3: Полный пайплайн")
    print("=" * 50)

    try:
        from post_queue import PostQueue
        from telegram_bot import TelegramSender

        queue = PostQueue()

        # Добавляем тестовый пост
        test_post = {
            "text": "🤖 *AI-находка дня: Test Tool*\n\nЭто тестовый пост для проверки пайплайна с картинками!\n\n🔗 [Читать](https://example.com)",
            "article_url": "https://example.com/test-pipeline",
            "article_title": "Test Pipeline Article",
            "image_prompt": "Минималистичная иконка тестирования, flat design, синие и зеленые тона",
            "format": "ai_tool",
        }

        post_id = queue.add_post(
            post_text=test_post["text"],
            article_url=test_post["article_url"],
            article_title=test_post["article_title"],
            image_prompt=test_post["image_prompt"],
            format_type=test_post["format"],
        )
        print(f"✅ Добавлен тестовый пост: id={post_id}")

        # Получаем пост
        post = queue.get_next_pending()
        if not post:
            print("❌ Пост не найден в очереди")
            return False

        print(f"   Текст: {post['post_text'][:50]}...")
        print(f"   Image prompt: {post['image_prompt'][:50]}...")

        # Генерируем картинку
        print("\nГенерирую картинку для поста...")
        from image_generator import get_image_generator

        generator = get_image_generator()
        image_path = generator.generate_for_post(
            post_id=post["id"],
            image_prompt=post["image_prompt"],
            category=post.get("format"),
        )

        if image_path:
            queue.update_image_url(post["id"], image_path)
            print(f"✅ Картинка сгенерирована: {image_path}")
        else:
            print("⚠️ Картинка не сгенерирована, продолжаем без неё")

        # Отправляем пользователю (не в канал, чтобы не спамить)
        sender = TelegramSender()

        if image_path:
            print("\nОтправляю пост с картинкой пользователю...")
            success = sender.send_photo(image_path, post["post_text"])
        else:
            print("\nОтправляю пост без картинки пользователю...")
            success = sender.send_message(post["post_text"])

        if success:
            queue.mark_published(post["id"])
            print("✅ Пост успешно отправлен!")
        else:
            queue.mark_failed(post["id"], "Test failed")
            print("❌ Ошибка отправки поста")

        # Статистика
        stats = queue.get_stats()
        print(f"\nСтатистика очереди: {stats}")

        return success

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Запуск тестов."""
    print("🚀 Запуск тестов пайплайна news-assistant-bot")
    print("=" * 60)

    # Тест 1: ImageGenerator
    image_path = test_image_generator()

    # Тест 2: TelegramSender
    test_telegram_sender(image_path)

    # Тест 3: Полный пайплайн
    test_full_pipeline()

    print("\n" + "=" * 60)
    print("✅ Тесты завершены!")


if __name__ == "__main__":
    main()
