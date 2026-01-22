"""Генератор изображений через GPT Image 1 Mini."""

import base64
import os
from pathlib import Path
from typing import Optional
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
                n=1,
                size=self.size,
                quality=self.quality,
                response_format="b64_json"
            )

            # Декодируем base64
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


# Singleton
_generator: Optional[ImageGenerator] = None


def get_image_generator() -> ImageGenerator:
    """Получить экземпляр генератора."""
    global _generator
    if _generator is None:
        _generator = ImageGenerator()
    return _generator
