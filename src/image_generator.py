"""Генератор изображений через GPT Image 1 (KLYMO Business Pivot)."""

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

# KLYMO Visual Style — Modern 3D render, как у Apple/Google tech blogs
KLYMO_VISUAL_STYLE = (
    "Style: Modern clean 3D render, photorealistic materials, soft studio lighting. "
    "Like Apple or Google product photography — premium, minimal, elegant. "
    "Shallow depth of field, soft shadows, subtle reflections. "
    "Draw SPECIFIC recognizable objects related to the article topic. "
    "Vary color palettes between images — not always the same colors. "
    "Clean background — solid gradient or soft blur. "
    "No text, no watermarks, no people, no faces, no hands. "
    "Square 1024x1024, centered composition."
)


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
        Сгенерировать изображение в KLYMO стиле.

        Args:
            prompt: Текстовый промпт для генерации
            category: Рубрика (ai_news, tool_review, case_study, etc.)
            filename: Имя файла для сохранения (без расширения)

        Returns:
            Путь к сохранённому файлу или None при ошибке
        """
        # Строим промпт: KLYMO стиль + описание сцены от Claude
        prompt = f"{KLYMO_VISUAL_STYLE}\n\nScene: {prompt}"

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
        OG-first стратегия: сначала берём картинку из статьи (бесплатно),
        генерируем через AI только если OG нет или она слишком мелкая.

        Args:
            og_image_url: URL OG-картинки из статьи
            image_prompt: Промпт для AI-генерации (fallback)
            category: Рубрика
            post_id: ID поста для имени файла

        Returns:
            (path_to_image, source_type)
            source_type: 'og', 'generated', 'none'
        """
        MIN_IMAGE_SIZE_KB = 15  # Картинки <15KB — скорее всего placeholder/иконка

        # Step 1: Пробуем OG-картинку из статьи
        if og_image_url and og_image_url.startswith(("http://", "https://")):
            try:
                from og_parser import download_image
                local_path = download_image(og_image_url)
                if local_path:
                    # Проверяем размер — мелкие картинки отбрасываем
                    file_size_kb = os.path.getsize(local_path) / 1024
                    if file_size_kb >= MIN_IMAGE_SIZE_KB:
                        logger.info(f"Using OG image ({file_size_kb:.0f}KB): {local_path}")
                        return (local_path, "og")
                    else:
                        logger.info(f"OG image too small ({file_size_kb:.0f}KB), skipping")
                        os.remove(local_path)
            except Exception as e:
                logger.warning(f"Failed to download OG image: {e}")

        # Step 2: Fallback — генерируем через GPT Image 1
        if image_prompt or category:
            try:
                filename = f"post_{post_id}" if post_id else None
                local_path = self.generate(image_prompt or "", category, filename)
                if local_path:
                    logger.info(f"Generated AI image: {local_path}")
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
