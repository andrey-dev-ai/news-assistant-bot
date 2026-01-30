"""Generate individual posts from news articles for @ai_dlya_doma channel."""

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from anthropic import (
    Anthropic,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from logger import get_logger

logger = get_logger("news_bot.post_generator")


def parse_classifier_response(response_text: str) -> dict:
    """
    Parse classifier response with error handling.
    Returns default response if LLM returned invalid JSON.
    """
    DEFAULT_RESPONSE = {
        "relevant": False,
        "confidence": 0,
        "category": "parse_error",
        "format": "ai_tool",
        "reason": "Failed to parse LLM response",
        "needs_review": True,
        "url_check_needed": True,
    }

    try:
        # Remove markdown code blocks if present
        cleaned = re.sub(r"^```json\s*", "", response_text.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)

        # Try to find JSON in text
        json_match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group()

        data = json.loads(cleaned)

        # Validate required fields
        if "relevant" not in data or "confidence" not in data:
            data = DEFAULT_RESPONSE.copy()
            data["reason"] = "Missing required fields"
            return data

        # Normalize confidence to 0-100
        data["confidence"] = max(0, min(100, int(data.get("confidence", 0))))

        # Defaults for optional fields
        data.setdefault("category", "unknown")
        data.setdefault("format", "ai_tool")
        data.setdefault("reason", "")
        data.setdefault("needs_review", data["confidence"] < 70)
        data.setdefault("url_check_needed", False)

        return data

    except (json.JSONDecodeError, TypeError, ValueError) as e:
        response = DEFAULT_RESPONSE.copy()
        response["reason"] = f"JSON parse error: {str(e)[:50]}"
        return response


def validate_telegram_html(text: str) -> str:
    """
    Validate and fix common HTML issues for Telegram.

    Telegram supports: <b>, <i>, <u>, <s>, <code>, <pre>, <a href="">
    """
    if not text:
        return text

    # Allowed Telegram HTML tags
    allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']

    # Count open and close tags
    for tag in allowed_tags:
        open_count = len(re.findall(rf'<{tag}[^>]*>', text, re.IGNORECASE))
        close_count = len(re.findall(rf'</{tag}>', text, re.IGNORECASE))

        # If imbalanced, try to fix or remove
        if open_count != close_count:
            logger.warning(f"HTML tag <{tag}> imbalanced: {open_count} open, {close_count} close")
            # Remove all instances of this tag if imbalanced
            text = re.sub(rf'<{tag}[^>]*>', '', text, flags=re.IGNORECASE)
            text = re.sub(rf'</{tag}>', '', text, flags=re.IGNORECASE)

    # Fix common LLM mistakes with <a> tags
    # Fix: <a href = "url"> → <a href="url">
    text = re.sub(r'<a\s+href\s*=\s*["\']([^"\']+)["\']>', r'<a href="\1">', text)

    # Fix: missing quotes around href
    text = re.sub(r'<a\s+href=([^"\'\s>]+)>', r'<a href="\1">', text)

    # Remove any unsupported HTML tags
    text = re.sub(r'<(?!/?(?:b|i|u|s|code|pre|a)[^>]*>)[^>]+>', '', text)

    return text.strip()


class PostFormat(Enum):
    """Types of posts for the channel."""
    AI_TOOL = "ai_tool"          # AI-находка дня
    QUICK_TIP = "quick_tip"      # Быстрый совет
    PROMPT_DAY = "prompt_day"    # Промт дня
    COMPARISON = "comparison"    # Сравнение
    CHECKLIST = "checklist"      # Чек-лист


@dataclass
class GeneratedPost:
    """A generated post ready for publication."""
    text: str
    format: PostFormat
    article_url: str
    article_title: str
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None  # OG/RSS image URL from article


class PostGenerator:
    """Generate beautiful posts for Telegram channel."""

    def __init__(self, api_key: str = None):
        """Initialize with Anthropic API."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        self.client = Anthropic(api_key=self.api_key)
        self.haiku_model = "claude-3-haiku-20240307"
        self.sonnet_model = "claude-sonnet-4-20250514"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(
            (RateLimitError, APIConnectionError, APITimeoutError)
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Claude API retry {retry_state.attempt_number}: "
            f"{retry_state.outcome.exception()}"
        ),
    )
    def _call_api(self, model: str, prompt: str, max_tokens: int = 1000) -> str:
        """Call Claude API with retry."""
        message = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def classify_article(self, article: Dict) -> Optional[Dict]:
        """
        Classify if article is relevant for the channel.
        Uses Haiku for cost efficiency.

        Returns:
            Dict with {relevant: bool, confidence: int, category: str, format: str,
                       reason: str, needs_review: bool, url_check_needed: bool}
            or None if error
        """
        title = article.get("title", "")
        description = article.get("summary", "")[:500]

        prompt = f"""Ты — классификатор контента для Telegram-канала "AI для дома".

ЦЕЛЕВАЯ АУДИТОРИЯ:
- Все, кто интересуется AI и хочет использовать его в жизни
- Не только технари — обычные люди тоже
- Интересует: что нового в мире AI, какие инструменты появились, что изменилось

ВКЛЮЧАТЬ (relevant: true):
- AI-инструменты любого типа (ChatGPT, Claude, Midjourney, Runway и др.)
- Новости AI-компаний (OpenAI, Anthropic, Google, Meta, Microsoft)
- Обновления моделей (GPT-5, Claude 4, Gemini 2, Llama 4 и др.)
- Тренды в AI: что меняется, куда движется индустрия
- Интересные применения AI (кейсы, примеры использования)
- Сравнения инструментов
- AI в повседневной жизни
- Новые функции в существующих сервисах

ИСКЛЮЧАТЬ (relevant: false):
- Чисто техническая документация (API docs, SDK reference)
- Код, туториалы для программистов
- Только финансовые новости (инвестиции без продукта/функции)
- Статьи старше 7 дней (проверь дату если указана)
- Криптовалюта, NFT, blockchain (если не связано с AI)
- Научные статьи без практической пользы
- Вакансии, найм

EDGE-CASES:
- "OpenAI raises $10B" → ИСКЛЮЧИТЬ (только финансы)
- "OpenAI launches new feature" → ВКЛЮЧИТЬ
- "How to build AI agent" (для разработчиков) → ИСКЛЮЧИТЬ
- "Best AI tools for 2025" → ВКЛЮЧИТЬ
- "New Claude model" → ВКЛЮЧИТЬ
- Пустое описание → снизь confidence на 20

FALLBACK:
- Не уверен → confidence < 70
- На грани → relevant: true, confidence: 55-65, needs_review: true
- Нет категории → category: "news"

СТАТЬЯ:
Заголовок: {title}
Источник: {article.get('source', '')}
Описание: {description}
Ссылка: {article.get('link', '')}

Определи:
1. Релевантна ли статья?
2. Уверенность (0-100)
3. Категория (tool/news/update/trend/comparison/tip)
4. Причина (кратко на русском)

Ответь ТОЛЬКО валидным JSON без markdown:
{{"relevant": true/false, "confidence": 0-100, "category": "...", "reason": "...", "needs_review": false, "url_check_needed": false}}"""

        try:
            response = self._call_api(self.haiku_model, prompt, max_tokens=250)
            result = parse_classifier_response(response)

            # Log classification result
            if result.get("needs_review"):
                logger.info(
                    f"Needs review: {title[:50]}... "
                    f"(confidence: {result.get('confidence')}, reason: {result.get('reason')})"
                )

            return result
        except Exception as e:
            logger.error(f"Error classifying article: {e}")
            return None

    def generate_post(self, article: Dict, post_format: PostFormat) -> Optional[GeneratedPost]:
        """
        Generate a post from article in specified format.
        Uses Sonnet for quality.
        """
        format_templates = {
            PostFormat.AI_TOOL: self._get_ai_tool_prompt(article),
            PostFormat.QUICK_TIP: self._get_quick_tip_prompt(article),
            PostFormat.PROMPT_DAY: self._get_prompt_day_prompt(article),
        }

        prompt = format_templates.get(post_format)
        if not prompt:
            logger.error(f"Unknown format: {post_format}")
            return None

        try:
            response = self._call_api(self.sonnet_model, prompt, max_tokens=800)

            # Parse response (expecting JSON with text and image_prompt)
            try:
                # Clean markdown code blocks if present
                cleaned = response.strip()
                cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"^```\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

                # Try to find JSON object in response with nested braces support
                json_match = re.search(r'\{.*?"text"\s*:\s*".*?\}', cleaned, re.DOTALL)
                if json_match:
                    # Extract the full JSON object including nested content
                    brace_count = 0
                    start_idx = json_match.start()
                    for i, char in enumerate(cleaned[start_idx:], start=start_idx):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                cleaned = cleaned[start_idx:i+1]
                                break

                data = json.loads(cleaned)
                text = data.get("text")
                image_prompt = data.get("image_prompt")

                # Fallback if text extraction failed
                if not text:
                    logger.warning("JSON parsed but 'text' field empty, using raw response")
                    text = response

            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning(f"Failed to parse post JSON: {e}, using raw response")
                text = response
                image_prompt = None

            # Validate and fix HTML before returning
            text = validate_telegram_html(text)

            return GeneratedPost(
                text=text,
                format=post_format,
                article_url=article.get("link", ""),
                article_title=article.get("title", ""),
                image_prompt=image_prompt,
                image_url=article.get("image_url"),  # OG/RSS image from article
            )
        except Exception as e:
            logger.error(f"Error generating post: {e}")
            return None

    def _get_ai_tool_prompt(self, article: Dict) -> str:
        """Prompt for AI-находка дня format."""
        article_link = article.get('link', '')
        return f"""Ты — копирайтер Telegram-канала "AI для мамы".

ЦЕЛЕВАЯ АУДИТОРИЯ: женщины 25-45, НЕ технари. Хотят упростить быт через AI.

СТИЛЬ:
- Дружелюбный, как совет от подруги
- БЕЗ технического жаргона
- Эмодзи: 1-2 штуки, по делу
- Обращение на "ты"
- Короткие предложения
- Максимум 350 символов

АНТИ-ПАТТЕРНЫ (никогда не используй):
- "Нейросеть" → заменяй на "AI"
- "Революционный", "уникальный", "лучший" → убирай
- Начало с "Представляем..." или "Встречайте..." → начинай с сути
- "Цена: уточняй на сайте" → ВООБЩЕ НЕ ПИШИ если нет цены
- Реакции типа "🔥 — уже пробовала" → НЕ ДОБАВЛЯЙ
- ГОЛЫЕ URL — НИКОГДА не пиши URL как есть, только через HTML-ссылку

СТАТЬЯ ДЛЯ ОБРАБОТКИ:
Заголовок: {article.get('title', '')}
Описание: {article.get('summary', '')[:500]}
Ссылка: {article_link}

ФОРМАТ ПОСТА (HTML-разметка для Telegram):
```
🤖 <b>[Название инструмента]</b>

[Что делает — 1-2 фразы]

[Зачем нужно тебе — 1 фраза]

[Только если ТОЧНО известна цена: 💰 Бесплатно / $X/мес]

👉 <a href="{article_link}">Попробовать</a>
```

ВАЖНО О ССЫЛКАХ:
- НИКОГДА не пиши голый URL
- Используй ТОЛЬКО HTML-формат: <a href="URL">текст</a>
- Текст ссылки: "Попробовать", "Смотреть", "Открыть"
- URL бери из статьи: {article_link}

Ответ ТОЛЬКО в формате JSON без markdown блоков:
{{"text": "готовый пост с HTML-разметкой", "image_prompt": "DALL-E prompt in English, flat design, pastel colors, 40 words max"}}"""

    def _get_quick_tip_prompt(self, article: Dict) -> str:
        """Prompt for Быстрый совет format."""
        article_link = article.get('link', '')
        return f"""Ты — копирайтер Telegram-канала "AI для мамы".

ЦЕЛЕВАЯ АУДИТОРИЯ: женщины 25-45, НЕ технари.

СТИЛЬ: короткий совет, 200-250 символов, без воды

СТАТЬЯ:
Заголовок: {article.get('title', '')}
Описание: {article.get('summary', '')[:500]}
Ссылка: {article_link}

ФОРМАТ (HTML-разметка для Telegram):
```
⚡ <b>[Заголовок совета]</b>

[Что сделать — 1-2 предложения]

✨ [Результат — что получишь]

👉 <a href="{article_link}">Подробнее</a>
```

ВАЖНО О ССЫЛКАХ:
- НИКОГДА не пиши голый URL
- Используй ТОЛЬКО: <a href="URL">текст</a>

Ответ ТОЛЬКО JSON без markdown:
{{"text": "готовый пост с HTML", "image_prompt": "DALL-E prompt in English, flat design, pastel colors, 40 words"}}"""

    def _get_prompt_day_prompt(self, article: Dict) -> str:
        """Prompt for Промт дня format."""
        return f"""Ты — копирайтер Telegram-канала "AI для мамы".

ЦЕЛЕВАЯ АУДИТОРИЯ: женщины 25-45, НЕ технари.

СТИЛЬ: короткий полезный промт, 300-350 символов

СТАТЬЯ:
Заголовок: {article.get('title', '')}
Описание: {article.get('summary', '')[:500]}

ФОРМАТ (HTML-разметка для Telegram):
```
🎯 <b>[Тема промта]</b>

<b>Промт:</b>
<code>[готовый промт на русском, можно скопировать]</code>

✨ [Что получишь — 1 фраза]
```

ВАЖНО:
- Промт оберни в <code></code> — так удобно копировать
- Заголовки в <b></b>

Ответ ТОЛЬКО JSON без markdown:
{{"text": "готовый пост с HTML", "image_prompt": "DALL-E prompt in English, flat design, pastel colors, 40 words"}}"""

    def generate_image_prompt(self, post: GeneratedPost) -> str:
        """
        Generate DALL-E prompt for post image.
        Uses Haiku for cost efficiency.
        """
        if post.image_prompt:
            return post.image_prompt

        prompt = f"""Create a DALL-E 3 image prompt for this Telegram post:

POST:
{post.text[:300]}

STYLE REQUIREMENTS:
- Flat design with soft gradients
- Pastel colors: light blue, pink, mint, lavender
- Minimalist icons
- Isometric perspective
- NO text on image
- NO people faces
- Cozy, friendly feeling
- Modern, clean look

Format: 1024x1024, English, 50-80 words.

Respond with ONLY the prompt, no explanations."""

        try:
            return self._call_api(self.haiku_model, prompt, max_tokens=150)
        except Exception as e:
            logger.error(f"Error generating image prompt: {e}")
            return "Flat design illustration, pastel colors, minimalist icons, cozy modern aesthetic, soft gradients, no text"

    def filter_and_rank_articles(
        self, articles: List[Dict], max_posts: int = 5
    ) -> List[tuple]:
        """
        Filter relevant articles and rank by confidence.

        Returns:
            List of (article, classification) tuples, sorted by confidence
        """
        classified = []

        for article in articles:
            result = self.classify_article(article)
            if result and result.get("relevant") and result.get("confidence", 0) >= 45:
                classified.append((article, result))
                logger.info(
                    f"Relevant: {article.get('title', '')[:50]}... "
                    f"(confidence: {result.get('confidence')})"
                )

        # Sort by confidence, take top N
        classified.sort(key=lambda x: x[1].get("confidence", 0), reverse=True)
        return classified[:max_posts]

    def generate_daily_posts(
        self, articles: List[Dict], count: int = 5
    ) -> List[GeneratedPost]:
        """
        Generate posts for the day from articles.

        Args:
            articles: List of news articles
            count: Number of posts to generate

        Returns:
            List of GeneratedPost objects
        """
        logger.info(f"Generating {count} posts from {len(articles)} articles")

        # Filter and rank articles
        ranked = self.filter_and_rank_articles(articles, max_posts=count)

        if not ranked:
            logger.warning("No relevant articles found")
            return []

        posts = []
        for article, classification in ranked:
            format_str = classification.get("format", "ai_tool")
            try:
                post_format = PostFormat(format_str)
            except ValueError:
                post_format = PostFormat.AI_TOOL

            post = self.generate_post(article, post_format)
            if post:
                # Generate image prompt if not present
                if not post.image_prompt:
                    post.image_prompt = self.generate_image_prompt(post)
                posts.append(post)
                logger.info(f"Generated post: {post.format.value}")

        return posts


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    generator = PostGenerator()

    # Test with dummy article
    test_article = {
        "title": "Canva launches AI photo editor for Instagram",
        "source": "TechCrunch",
        "summary": "Canva announced a new AI-powered photo editor that can automatically enhance photos, remove backgrounds, and suggest Instagram-ready filters. The tool is free for basic use.",
        "link": "https://example.com/canva-ai",
    }

    print("Testing classification...")
    result = generator.classify_article(test_article)
    print(f"Classification: {result}")

    if result and result.get("relevant"):
        print("\nGenerating post...")
        post = generator.generate_post(test_article, PostFormat.AI_TOOL)
        if post:
            print(f"\n{post.text}")
            print(f"\nImage prompt: {post.image_prompt}")
