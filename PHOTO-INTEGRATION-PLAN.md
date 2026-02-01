# План интеграции фотографий в news-assistant-bot

**Дата:** 2026-02-01
**Статус:** ✅ ВЫПОЛНЕНО (2026-02-01)

---

## Контекст задачи

**Проект:** news-assistant-bot для канала @ai_dlya_doma
**ЦА:** женщины 25-45, быт, дом (НЕ технари)
**Текущее состояние:** публикуются только тексты, фото не работают

**Что нужно:**
- Умный выбор изображения: OG если качественное, иначе генерация
- Минимальный размер: 800px
- Новые промпты для генерации (soft 3D, без роботов)
- Превью изображений в модерации

---

## Файлы для изменения

| Файл | Что делаем |
|------|-----------|
| `config/prompts.yaml` | Заменить image_templates на новые промпты |
| `src/og_parser.py` | Добавить check_image_quality() — проверка размера |
| `src/image_generator.py` | Добавить choose_image_strategy() — умный выбор |
| `scheduler.py` | Интегрировать новую логику в публикацию |
| `src/telegram_bot.py` | Добавить превью изображений в модерации |
| `requirements.txt` | Добавить Pillow>=10.0.0 |

---

## 1. Новые промпты (config/prompts.yaml)

Заменить секцию `image_templates`. Стиль:
- **Soft 3D render** (не flat, не роботы)
- **Тёплые пастельные цвета**: cream, peach, sage green, dusty rose
- **БЕЗ людей и лиц**
- **Уютная атмосфера**

```yaml
image_templates:
  base_style: |
    Style: Soft 3D render, modern minimalist aesthetic.
    Colors: Warm pastels — cream white, soft peach, sage green, dusty rose, light blue.
    Mood: Cozy, approachable, professional.
    Lighting: Soft ambient light, gentle shadows.
    Technical: No text, no watermarks, no people, no faces.
    Format: Square 1024x1024, centered composition.

  kitchen: |
    A cozy kitchen scene in soft 3D style.
    Scene: Modern kitchen counter with fresh ingredients — colorful vegetables, herbs in pots, a wooden cutting board. A tablet or smartphone showing a recipe app with a friendly AI assistant icon on screen. Steam rising from a cooking pot.
    Style: Soft 3D render, warm pastels — cream, peach, sage green. Warm ambient lighting like morning sun through a window.
    Mood: Inviting, helpful, homey.
    Technical: No text, no people, no faces. Square 1024x1024.

  kids: |
    A playful learning corner in soft 3D style.
    Scene: Cozy reading nook with colorful books, building blocks, a tablet showing an educational app with friendly cartoon characters. Soft plush toys, a small chalkboard with doodles.
    Style: Soft 3D render, playful pastels — lavender, soft yellow, mint green, baby blue.
    Mood: Safe, nurturing, fun, educational.
    Technical: No children, no people, no faces. Square 1024x1024.

  home: |
    An organized living space in soft 3D style.
    Scene: Modern minimalist room with smart home elements — a voice assistant device, organized shelves, plants, natural light. Clean surfaces, cozy textures.
    Style: Soft 3D render, calming pastels — sage green, warm grey, cream, terracotta accents.
    Mood: Calm, organized, achievable, inspiring.
    Technical: No people, no faces. Focus on space and organization. Square 1024x1024.

  finance: |
    A personal finance workspace in soft 3D style.
    Scene: Cozy desk with a piggy bank, a smartphone showing a budget app, coins organized in stacks, a small plant, notebook with financial notes. Coffee cup nearby.
    Style: Soft 3D render, optimistic pastels — mint green, coral, warm white, soft gold accents.
    Mood: Positive, empowering, not stressful.
    Technical: No people, no faces, no specific currency symbols. Square 1024x1024.

  planning: |
    A productivity workspace in soft 3D style.
    Scene: Clean desk with an open planner, colorful sticky notes, a tablet showing a to-do app, a cup of coffee, small potted succulent. Morning light atmosphere.
    Style: Soft 3D render, productive pastels — sky blue, peach, cream, warm grey.
    Mood: Focused but calm, balanced, achievable productivity.
    Technical: No people, no faces, no readable text on planner. Square 1024x1024.

  tool_review: |
    A tech showcase scene in soft 3D style.
    Scene: Modern workspace with a laptop showing an AI interface, floating UI elements, holographic icons representing AI capabilities — chat bubbles, magic wand, lightbulb.
    Style: Soft 3D render, tech-modern pastels — blue, purple, white, with subtle glow effects.
    Mood: Innovative, accessible, exciting.
    Technical: No people, no faces, no readable text. Square 1024x1024.

  news: |
    A news and updates scene in soft 3D style.
    Scene: Abstract representation of news flow — floating newspaper elements, notification bells, speech bubbles, connected nodes representing AI networks. Digital globe in background.
    Style: Soft 3D render, professional pastels — blue, teal, white, subtle orange accents.
    Mood: Informative, trustworthy, current.
    Technical: No people, no faces, no readable text. Square 1024x1024.

  prompt_home: |
    A creative prompt workspace in soft 3D style.
    Scene: Magical desk with a glowing text box (prompt input), sparkles, lightbulbs, floating ideas as abstract shapes. A smartphone showing AI chat interface.
    Style: Soft 3D render, creative pastels — lavender, pink, soft gold, white.
    Mood: Creative, inspiring, magical but practical.
    Technical: No people, no faces, no readable text. Square 1024x1024.

  lifehack: |
    A clever solution scene in soft 3D style.
    Scene: Before-and-after visualization — messy desk transforming into organized one, with AI magic sparkles in between. Timer, checkmarks, efficiency symbols.
    Style: Soft 3D render, achievement pastels — green, gold, white, soft orange.
    Mood: Satisfying, clever, time-saving.
    Technical: No people, no faces. Square 1024x1024.

  free_service: |
    A gift/free offer scene in soft 3D style.
    Scene: Open gift box with AI tool icons floating out — chat bubbles, image icons, document icons. "Free" badge ribbon, sparkles, celebration confetti.
    Style: Soft 3D render, generous pastels — coral, mint, gold accents, white.
    Mood: Generous, exciting, accessible.
    Technical: No people, no faces, no text except decorative patterns. Square 1024x1024.

  collection: |
    A curated collection scene in soft 3D style.
    Scene: Shelf display with 5 app icons or tool cards, each with distinct color. Star ratings, bookmarks.
    Style: Soft 3D render, organized pastels — various harmonious colors, white background.
    Mood: Curated, helpful, comprehensive.
    Technical: No people, no faces, no readable text. Square 1024x1024.

  digest: |
    A weekly summary scene in soft 3D style.
    Scene: Calendar page with highlighted week, surrounded by floating summary cards, charts, key highlights as icons. Clock showing time saved.
    Style: Soft 3D render, summary pastels — blue, green, white, subtle yellow accents.
    Mood: Comprehensive, valuable, time-efficient.
    Technical: No people, no faces, no readable text. Square 1024x1024.
```

---

## 2. Проверка качества изображений (src/og_parser.py)

Добавить функцию:

```python
from PIL import Image
from io import BytesIO

MIN_WIDTH = 800
MIN_HEIGHT = 600

def check_image_quality(image_url: str, min_width: int = 800, min_height: int = 600) -> dict:
    """
    Проверить качество изображения по URL.

    Returns:
        {"is_valid": bool, "width": int, "height": int, "reason": str}
    """
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=10, stream=True)
        response.raise_for_status()

        content_length = int(response.headers.get('content-length', 0))
        if content_length > 10 * 1024 * 1024:  # > 10MB
            return {"is_valid": False, "reason": "File too large"}

        img_data = BytesIO(response.content)
        img = Image.open(img_data)
        width, height = img.size

        if width < min_width:
            return {"is_valid": False, "width": width, "height": height,
                    "reason": f"Width {width}px < {min_width}px minimum"}

        if height < min_height:
            return {"is_valid": False, "width": width, "height": height,
                    "reason": f"Height {height}px < {min_height}px minimum"}

        aspect_ratio = width / height
        if aspect_ratio > 3 or aspect_ratio < 0.33:
            return {"is_valid": False, "width": width, "height": height,
                    "reason": f"Bad aspect ratio: {aspect_ratio:.2f}"}

        return {"is_valid": True, "width": width, "height": height}

    except Exception as e:
        return {"is_valid": False, "reason": str(e)}
```

Расширить `_is_icon_or_logo()`:

```python
def _is_icon_or_logo(url: str) -> bool:
    url_lower = url.lower()
    bad_patterns = [
        "logo", "icon", "favicon", "avatar", "badge",
        "sprite", "button", "ad-", "banner", "pixel",
        ".svg", "1x1", "tracking", "placeholder",
        "default", "og-default", "social-default",
        "no-image", "noimage", "missing", "blank",
        "thumb_", "_thumb", "thumbnail", "mini",
        "gravatar", "profile", "user-avatar"
    ]
    return any(pattern in url_lower for pattern in bad_patterns)
```

---

## 3. Умный выбор изображения (src/image_generator.py)

Добавить метод:

```python
def choose_image_strategy(
    self,
    og_image_url: Optional[str],
    image_prompt: Optional[str],
    category: Optional[str] = None,
    post_id: Optional[int] = None
) -> Tuple[Optional[str], str]:
    """
    Умный выбор стратегии получения изображения.

    Returns:
        (path_to_image, source_type)
        source_type: 'og_image', 'generated', 'none'
    """
    from og_parser import check_image_quality, download_image, _is_icon_or_logo

    # Шаг 1: Проверяем OG-изображение
    if og_image_url:
        if _is_icon_or_logo(og_image_url):
            logger.info(f"OG image looks like logo/icon, will generate instead")
        else:
            quality = check_image_quality(og_image_url)

            if quality.get("is_valid"):
                local_path = download_image(og_image_url)
                if local_path:
                    logger.info(f"Using OG image: {quality['width']}x{quality['height']}")
                    return (local_path, "og_image")
            else:
                logger.info(f"OG image rejected: {quality.get('reason')}")

    # Шаг 2: Генерируем через AI
    if image_prompt or category:
        try:
            filename = f"post_{post_id}" if post_id else None
            local_path = self.generate(image_prompt or "", category, filename)
            if local_path:
                return (local_path, "generated")
        except Exception as e:
            logger.error(f"Failed to generate image: {e}")

    return (None, "none")
```

---

## 4. Интеграция в scheduler.py

В функции `publish_scheduled_post()`:

```python
# Умный выбор изображения
img_generator = get_image_generator()
image_path, source = img_generator.choose_image_strategy(
    og_image_url=post.get("image_url"),
    image_prompt=post.get("image_prompt"),
    category=post.get("format"),
    post_id=post["id"]
)

if image_path:
    queue.update_image_url(post["id"], image_path)
    logger.info(f"Image ready: {source} -> {image_path}")

# Отправка
if image_path:
    success = sender.send_photo_to_channel(image_path, post["post_text"])
else:
    success = sender.send_to_channel(post["post_text"])
```

---

## 5. Превью в модерации (src/telegram_bot.py)

В `_show_moderation_queue()` — отправлять `reply_photo()` вместо `reply_text()` если есть изображение.

---

## 6. Зависимости

```
# requirements.txt
Pillow>=10.0.0
```

---

## Деплой

```bash
# Загрузить файлы
scp "D:\AI\projects\news-assistant-bot\src\*.py" root@141.227.152.143:/opt/news-assistant-bot/src/
scp "D:\AI\projects\news-assistant-bot\config\prompts.yaml" root@141.227.152.143:/opt/news-assistant-bot/config/

# Установить зависимости и перезапустить
ssh root@141.227.152.143 "cd /opt/news-assistant-bot && pip install Pillow && systemctl restart ai-news-bot"

# Проверить
ssh root@141.227.152.143 "systemctl status ai-news-bot"
ssh root@141.227.152.143 "journalctl -u ai-news-bot -f"
```

---

## Проверка

1. Запустить бота локально
2. Нажать "Обновить" для генерации постов
3. Проверить превью в модерации
4. Опубликовать в тестовый канал
5. Проверить качество изображений
