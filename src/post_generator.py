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
from openai import OpenAI
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
        "audience": "unknown",
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
        data.setdefault("audience", "consumer")
        data.setdefault("format", "ai_tool")
        data.setdefault("reason", "")
        data.setdefault("needs_review", data["confidence"] < 70)
        data.setdefault("url_check_needed", False)

        # Filter out enterprise content
        audience = data.get("audience", "consumer").lower()
        if audience == "enterprise":
            data["relevant"] = False
            data["reason"] = f"Enterprise content filtered: {data.get('reason', '')}"
            logger.info(f"Filtered enterprise content: {data.get('reason', '')[:50]}")
        elif audience == "mixed":
            # Lower confidence for mixed audience
            data["confidence"] = max(0, data["confidence"] - 10)
            data["needs_review"] = True

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


def is_good_image(url: str) -> bool:
    """
    Check if OG-image URL is likely a good quality image.
    Returns False for placeholders, logos, icons, etc.
    """
    if not url:
        return False

    url_lower = url.lower()

    # Bad patterns - likely placeholders or low-quality images
    bad_patterns = [
        'placeholder', 'default', 'logo', 'icon', 'avatar',
        '1x1', '1x1.', 'pixel', 'blank', 'empty', 'spacer',
        'og-default', 'social-default', 'share-default',
        'no-image', 'noimage', 'missing'
    ]

    if any(pattern in url_lower for pattern in bad_patterns):
        return False

    # Check for valid image extension
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    has_valid_ext = any(url_lower.endswith(ext) or f'{ext}?' in url_lower
                        for ext in valid_extensions)

    # Some URLs don't have extensions but are still valid (e.g., CDN URLs)
    # Accept them if they don't match bad patterns
    if not has_valid_ext:
        # Check for common image CDN patterns
        cdn_patterns = ['cloudinary', 'imgix', 'cloudfront', 'akamai',
                        'fastly', 'cdn', 'images', 'media', 'assets']
        if not any(cdn in url_lower for cdn in cdn_patterns):
            return False

    return True


def generate_image_via_openai(prompt: str) -> Optional[str]:
    """
    Generate image using OpenAI DALL-E 3.
    Returns URL of generated image or None on error.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, cannot generate image")
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        return response.data[0].url
    except Exception as e:
        logger.error(f"OpenAI image generation failed: {e}")
        return None


def get_image_for_post(article: Dict, image_prompt: str = None) -> Tuple[Optional[str], str]:
    """
    Get image for post using hybrid approach:
    1. Try OG-image from article if it's good quality
    2. Fall back to OpenAI generation

    Returns:
        Tuple of (image_url, source_type)
        source_type: 'og_image', 'generated', or 'none'
    """
    # Try OG-image first
    og_image = article.get('image_url')
    if og_image and is_good_image(og_image):
        logger.info(f"Using OG-image: {og_image[:50]}...")
        return (og_image, 'og_image')

    # Generate if we have a prompt
    if image_prompt:
        logger.info("OG-image not suitable, generating via OpenAI...")
        generated_url = generate_image_via_openai(image_prompt)
        if generated_url:
            return (generated_url, 'generated')

    logger.warning("No image available for post")
    return (None, 'none')


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

ЦЕЛЕВАЯ АУДИТОРИЯ (CONSUMER):
- Обычные люди, НЕ программисты и НЕ корпоративные клиенты
- Используют AI для личных задач: дом, учёба, творчество, продуктивность
- Интересует: простые инструменты, новые функции, практические советы
- Язык: понятный, без технического жаргона

ВКЛЮЧАТЬ (relevant: true, audience: "consumer"):
- AI-инструменты для обычных людей (ChatGPT, Claude, Midjourney, Canva AI)
- Новости AI-компаний с практической пользой для пользователей
- Обновления моделей если это влияет на пользователей (новые функции, доступность)
- AI для дома, быта, учёбы, творчества, здоровья
- Бесплатные и доступные инструменты
- Сравнения для обычных пользователей
- Мобильные AI-приложения
- Голосовые ассистенты, умный дом

ИСКЛЮЧАТЬ (relevant: false) — ENTERPRISE/B2B контент:
- Решения для бизнеса: "enterprise", "B2B", "corporate", "business solution"
- Инфраструктура: "deployment", "infrastructure", "cloud", "MLOps", "kubernetes"
- Разработка: API, SDK, framework, library, open-source (для разработчиков)
- Научные статьи: arxiv, research paper, benchmark, model architecture
- Финансы без продукта: "raises $X", "funding round", "valuation"
- HR/найм: "hiring", "joins", "appointed"
- Security/compliance: "SOC2", "HIPAA", "enterprise security"
- Аналитика рынка: "market share", "industry report"
- Партнёрства B2B: "partnership with [enterprise company]"

ПРИМЕРЫ:
✅ "ChatGPT can now edit images" → consumer, практично
✅ "New free AI tool for photo editing" → consumer, бесплатно
✅ "Claude теперь доступен в мобильном приложении" → consumer
❌ "OpenAI launches enterprise API tier" → enterprise
❌ "New ML framework for developers" → developer
❌ "Anthropic raises $2B at $15B valuation" → finance only
❌ "AWS announces AI infrastructure updates" → enterprise
❌ "How to fine-tune LLaMA with LoRA" → developer

EDGE-CASES:
- Новая модель (GPT-5, Claude 4) → ВКЛЮЧИТЬ если про функции для пользователей
- Новое API → ИСКЛЮЧИТЬ (для разработчиков)
- Цены упали → ВКЛЮЧИТЬ если для consumer
- Научный прорыв → ВКЛЮЧИТЬ только если практическое применение понятно

FALLBACK:
- Сомневаешься в аудитории → audience: "mixed", снизь confidence на 15
- Непонятно enterprise или consumer → needs_review: true
- Пустое описание → confidence -= 20

СТАТЬЯ:
Заголовок: {title}
Источник: {article.get('source', '')}
Описание: {description}
Ссылка: {article.get('link', '')}

Определи:
1. Релевантна для CONSUMER аудитории?
2. Уверенность (0-100)
3. Категория (tool/news/update/trend/comparison/tip)
4. Аудитория (consumer/enterprise/mixed)
5. Причина (кратко на русском)

Ответь ТОЛЬКО валидным JSON без markdown:
{{"relevant": true/false, "confidence": 0-100, "category": "...", "audience": "consumer/enterprise/mixed", "reason": "...", "needs_review": false, "url_check_needed": false}}"""

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

    def generate_post(self, article: Dict, post_format: PostFormat = None) -> Optional[GeneratedPost]:
        """
        Generate a post from article using universal long-form format.
        Uses Sonnet for quality.

        Note: post_format is kept for backward compatibility but not used.
        All posts now use the same universal format (700-900 chars).
        """
        prompt = self._get_universal_prompt(article)

        try:
            # Increased max_tokens for longer posts
            response = self._call_api(self.sonnet_model, prompt, max_tokens=1500)

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
                format=post_format or PostFormat.AI_TOOL,
                article_url=article.get("link", ""),
                article_title=article.get("title", ""),
                image_prompt=image_prompt,
                image_url=article.get("image_url"),  # OG/RSS image from article
            )
        except Exception as e:
            logger.error(f"Error generating post: {e}")
            return None

    def _get_universal_prompt(self, article: Dict) -> str:
        """
        Universal prompt for long-form posts (1500-2000 chars).
        Style: Databoard-inspired, links embedded in text.
        """
        article_link = article.get('link', '')
        source_name = article.get('source', 'источник')

        return f"""Ты — копирайтер Telegram-канала "AI для дома" (@ai_dlya_doma).

АУДИТОРИЯ:
- Все, кто интересуется AI и хочет применять его в жизни
- Не только программисты — обычные люди тоже
- Ценят: актуальность, практическую пользу, конкретику

СТИЛЬ:
- Информативный, энергичный, но без кликбейта
- Эмодзи: 1-2 штуки, только в заголовке
- Обращение: нейтральное или на "вы"
- Ссылки ВНУТРИ текста, не в конце
- Длина: 700-900 символов (это важно для Telegram caption!)

СТРУКТУРА ПОСТА:
```
[Эмодзи] <b>Заголовок — короткий, цепляющий</b>

Первый абзац — суть новости. О чём речь, почему это интересно. 2-3 предложения.

Второй абзац — детали. Что именно изменилось, как работает, какие функции. Здесь можно <a href="URL">вставить ссылку</a> на источник или сам сервис.

Третий абзац — контекст. Почему это важно, как это влияет на рынок/пользователей, что думают эксперты.

[Опционально] Четвёртый абзац — практический вывод или вопрос к читателям.
```

АНТИ-ПАТТЕРНЫ (НИКОГДА не используй):
- Шаблонные CTA типа "👉 Попробовать", "🔗 Ссылка"
- Голые URL без <a> тегов
- "Нейросеть" → используй "AI" или название модели
- "Революционный", "уникальный", "прорывной"
- Начало с "Представляем...", "Встречайте..."
- Список фич через буллеты в каждом посте
- Пустые обещания без конкретики

ПРАВИЛА ССЫЛОК:
- Ссылки встраивай В ТЕКСТ: <a href="URL">читайте подробнее</a>
- Текст ссылки должен быть осмысленным: "пишет TechCrunch", "сообщает компания"
- Можно добавить 1-2 ссылки, не больше
- Основная ссылка на источник: {article_link}

СТАТЬЯ ДЛЯ ОБРАБОТКИ:
Заголовок: {article.get('title', '')}
Источник: {source_name}
Описание: {article.get('summary', '')[:800]}
Ссылка: {article_link}

Ответ ТОЛЬКО JSON без markdown блоков:
{{"text": "готовый пост с HTML-разметкой, 700-900 символов", "image_prompt": "DALL-E prompt in English, tech illustration style, modern, clean, 40 words max"}}"""


    def generate_post_for_rubric(
        self, article: Dict, rubric_name: str
    ) -> Optional[GeneratedPost]:
        """
        Generate a post for a specific rubric using its template.

        Args:
            article: Article data
            rubric_name: Name of the rubric (e.g., 'tool_review', 'news')

        Returns:
            GeneratedPost or None
        """
        try:
            from rubrics import Rubric, RUBRIC_PROMPTS

            # Get rubric enum
            try:
                rubric = Rubric(rubric_name)
            except ValueError:
                logger.warning(f"Unknown rubric: {rubric_name}, using default")
                return self.generate_post(article)

            # Get rubric-specific prompt template
            rubric_template = RUBRIC_PROMPTS.get(rubric)
            if not rubric_template:
                logger.warning(f"No template for rubric: {rubric_name}, using default")
                return self.generate_post(article)

            # Build full prompt
            article_link = article.get('link', '')
            source_name = article.get('source', 'источник')

            prompt = f"""Ты — копирайтер Telegram-канала "AI для дома" (@ai_dlya_doma).

АУДИТОРИЯ: Все, кто интересуется AI — от новичков до продвинутых.

РУБРИКА И ФОРМАТ:
{rubric_template}

СТАТЬЯ ДЛЯ ОБРАБОТКИ:
Заголовок: {article.get('title', '')}
Источник: {source_name}
Описание: {article.get('summary', '')[:800]}
Ссылка: {article_link}

ПРАВИЛА:
- Используй HTML-разметку Telegram: <b>, <i>, <a href="">
- Ссылки встраивай в текст
- Длина: 700-900 символов
- Замени [URL] на реальную ссылку: {article_link}

Ответ ТОЛЬКО JSON:
{{"text": "готовый пост", "image_prompt": "DALL-E prompt, 40 words"}}"""

            response = self._call_api(self.sonnet_model, prompt, max_tokens=1500)

            # Parse response
            try:
                cleaned = response.strip()
                cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"^```\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

                data = json.loads(cleaned)
                text = data.get("text", response)
                image_prompt = data.get("image_prompt")
            except (json.JSONDecodeError, TypeError, ValueError):
                text = response
                image_prompt = None

            text = validate_telegram_html(text)

            # Map rubric to PostFormat
            format_map = {
                "tool_review": PostFormat.AI_TOOL,
                "news": PostFormat.AI_TOOL,
                "prompt_home": PostFormat.PROMPT_DAY,
                "lifehack": PostFormat.QUICK_TIP,
                "free_service": PostFormat.AI_TOOL,
                "collection": PostFormat.CHECKLIST,
                "digest": PostFormat.CHECKLIST,
            }
            post_format = format_map.get(rubric_name, PostFormat.AI_TOOL)

            return GeneratedPost(
                text=text,
                format=post_format,
                article_url=article.get("link", ""),
                article_title=article.get("title", ""),
                image_prompt=image_prompt,
                image_url=article.get("image_url"),
            )

        except Exception as e:
            logger.error(f"Error generating post for rubric {rubric_name}: {e}")
            return None

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
