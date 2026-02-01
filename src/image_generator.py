"""Генератор изображений через GPT Image 1 Mini."""

import base64
import os
from pathlib import Path
from typing import Optional, Tuple
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.config_loader import get_image_template
from src.logger import get_logger

logger = get_logger(__name__)


class ImageGenerator:
    """Генератор изображений через OpenAI GPT Image 1 Mini."""

    def __init__(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY не установлен в .env")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-image-1"  # GPT Image 1 Mini
        self.quality = "medium"
        self.size = "1024x1024"
        self.output_dir = Path("data/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def generate(
        self,
        prompt: str,
        category: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Optional[str]:
        """
        Сгенерировать изображение.

        Args:
            prompt: Текстовый промпт для генерации
            category: Категория для шаблона (kitchen, kids, home, finance, planning)
            filename: Имя файла для сохранения (без расширения)

        Returns:
            Путь к сохранённому файлу или None при ошибке
        """
        # Если есть категория, добавляем шаблон
        if category:
            template = get_image_template(category)
            if template:
                prompt = f"{template}\n\nДополнительно: {prompt}"

        logger.info(f"Генерирую изображение: {prompt[:100]}...")

        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=self.size,
                quality=self.quality
            )

            # Декодируем base64 (по умолчанию возвращается b64_json)
            image_data = base64.b64decode(response.data[0].b64_json)

            # Сохраняем
            if not filename:
                filename = f"img_{hash(prompt) % 100000}"
            filepath = self.output_dir / f"{filename}.png"

            with open(filepath, "wb") as f:
                f.write(image_data)

            logger.info(f"Изображение сохранено: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            raise

    def generate_for_post(
        self,
        post_id: int,
        image_prompt: str,
        category: Optional[str] = None
    ) -> Optional[str]:
        """Сгенерировать изображение для поста."""
        filename = f"post_{post_id}"
        return self.generate(image_prompt, category, filename)

    def choose_image_strategy(
        self,
        og_image_url: Optional[str],
        image_prompt: Optional[str],
        category: Optional[str] = None,
        post_id: Optional[int] = None
    ) -> Tuple[Optional[str], str]:
        """
        Умный выбор стратегии получения изображения.

        1. Если OG-изображение качественное (мин 800px) — используем его
        2. Иначе — генерируем через GPT Image

        Args:
            og_image_url: URL OG-изображения из источника
            image_prompt: Промпт для генерации (если потребуется)
            category: Категория контента для шаблона
            post_id: ID поста для имени файла

        Returns:
            (path_to_image, source_type)
            source_type: 'og_image', 'generated', 'none'
        """
        from src.og_parser import check_image_quality, download_image, _is_icon_or_logo

        # Шаг 1: Проверяем OG-изображение
        if og_image_url:
            if _is_icon_or_logo(og_image_url):
                logger.info(f"OG image looks like logo/icon, will generate instead")
            else:
                quality = check_image_quality(og_image_url)

                if quality.get("is_valid"):
                    local_path = download_image(og_image_url)
                    if local_path:
                        logger.info(
                            f"Using OG image: {quality['width']}x{quality['height']}"
                        )
                        return (local_path, "og_image")
                else:
                    logger.info(f"OG image rejected: {quality.get('reason')}")

        # Шаг 2: Генерируем через AI
        if image_prompt or category:
            try:
                filename = f"post_{post_id}" if post_id else None
                local_path = self.generate(image_prompt or "", category, filename)
                if local_path:
                    logger.info(f"Generated image: {local_path}")
                    return (local_path, "generated")
            except Exception as e:
                logger.error(f"Failed to generate image: {e}")

        return (None, "none")


# Singleton
_generator: Optional[ImageGenerator] = None


def get_image_generator() -> ImageGenerator:
    """Получить экземпляр генератора."""
    global _generator
    if _generator is None:
        _generator = ImageGenerator()
    return _generator
