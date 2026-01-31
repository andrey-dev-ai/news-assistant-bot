# Инструкция для продолжения работы — Phase 3

**Дата:** 2026-01-31
**Последний коммит:** см. git log

---

## Что сделано

### Phase 3 — Система модерации ✅

1. **Модерация (USE_MODERATION=true):**
   - `src/moderation.py` — workflow одобрения постов
   - Постоянная клавиатура (📋 Очередь, 📊 Статистика, 🔄 Обновить, ⚙️ Настройки)
   - Inline-кнопки под постами (✅ ❌ 📅 ✏️)
   - Статусы: pending → pending_approval → approved → published

2. **Рубрики (готово, не включено):**
   - `src/rubrics.py` — 10 рубрик
   - `config/content_plan.yaml` — недельное расписание
   - 15 RSS источников

3. **Исправления 2026-01-31:**
   - Посты 700-900 символов (Telegram caption limit = 1024)
   - **Исправлено превью в боте** — добавлена функция `strip_html_tags()` в `telegram_bot.py`
     - Проблема: обрезка HTML-текста ломала теги → ошибка "unclosed start tag"
     - Решение: удаление HTML-тегов перед обрезкой превью

---

## Текущая конфигурация на VPS

```bash
# /opt/news-assistant-bot/.env
USE_MODERATION=true      # ✅ Включено
USE_RUBRICS=false        # Готово, не включено
USE_NEW_SCHEDULE=false   # Готово, не включено
```

**VPS:** 141.227.152.143
**Путь:** /opt/news-assistant-bot/
**Сервис:** ai-news-bot

---

## ⚠️ ПРИОРИТЕТНАЯ ЗАДАЧА: Расширить RSS-источники

### Проблема
- Проверяется только **10 статей** из всех собранных
- Если среди топ-10 нет AI-релевантных — постов не будет (ошибка "Не удалось сгенерировать")
- 2 источника не работают (404): Ben's Bites, VC.ru AI
- Многие источники публикуют много НЕ-AI контента

### Решение (3 шага)

#### Шаг 1: Удалить нерабочие источники из `config/rss_feeds.json`
```json
// УДАЛИТЬ:
{
  "name": "Ben's Bites",
  "url": "https://rss.beehiiv.com/feeds/6RP9sQV5xC.xml"  // 404
},
{
  "name": "VC.ru AI",
  "url": "https://vc.ru/rss/ai"  // 404
}
```

#### Шаг 2: Добавить новые AI-источники в `config/rss_feeds.json`
```json
{
  "name": "TechCrunch AI",
  "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
  "enabled": true,
  "priority": 1,
  "comment": "AI новости от TechCrunch"
},
{
  "name": "VentureBeat AI",
  "url": "https://venturebeat.com/category/ai/feed/",
  "enabled": true,
  "priority": 1,
  "comment": "Enterprise AI новости"
},
{
  "name": "MIT Technology Review AI",
  "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
  "enabled": true,
  "priority": 2,
  "comment": "Глубокая аналитика AI"
},
{
  "name": "AI News",
  "url": "https://www.artificialintelligence-news.com/feed/",
  "enabled": true,
  "priority": 1,
  "comment": "Только AI новости"
},
{
  "name": "OpenAI Blog",
  "url": "https://openai.com/blog/rss.xml",
  "enabled": true,
  "priority": 1,
  "comment": "Официальные анонсы OpenAI"
},
{
  "name": "Anthropic News",
  "url": "https://www.anthropic.com/feed.xml",
  "enabled": true,
  "priority": 1,
  "comment": "Официальные анонсы Anthropic"
},
{
  "name": "Google AI Blog",
  "url": "https://blog.google/technology/ai/rss/",
  "enabled": true,
  "priority": 1,
  "comment": "Официальные анонсы Google AI"
},
{
  "name": "Hugging Face Blog",
  "url": "https://huggingface.co/blog/feed.xml",
  "enabled": true,
  "priority": 2,
  "comment": "Open source AI модели"
}
```

#### Шаг 3: Увеличить лимит проверяемых статей в `src/telegram_bot.py`
Найти строку (~520):
```python
unsent = parser.enrich_with_og_images(unsent[:10])  # Limit to avoid slowdown
```
Заменить на:
```python
unsent = parser.enrich_with_og_images(unsent[:25])  # Increased limit for better coverage
```

### Деплой после изменений
```bash
scp "D:\AI\projects\news-assistant-bot\config\rss_feeds.json" root@141.227.152.143:/opt/news-assistant-bot/config/
scp "D:\AI\projects\news-assistant-bot\src\telegram_bot.py" root@141.227.152.143:/opt/news-assistant-bot/src/
ssh root@141.227.152.143 "systemctl restart ai-news-bot"
```

### Верификация
```bash
# Проверить логи — новые источники должны загружаться
ssh root@141.227.152.143 "journalctl -u ai-news-bot --since '2 minutes ago' --no-pager"

# В боте нажать "Обновить" — должно быть больше релевантных статей
```

---

## Другие задачи (после RSS)

### Включить рубрики
```bash
# На сервере добавить в .env:
USE_RUBRICS=true
systemctl restart ai-news-bot
```

### Включить недельное расписание
```bash
USE_NEW_SCHEDULE=true
```
11 постов/неделю по расписанию из `config/content_plan.yaml`.

### Доделать аналитику (Этап 7)
- Создать `src/analytics.py`
- Добавить таблицы post_stats, daily_metrics
- Интегрировать сбор статистики

### Фильтрация контента
- Создать `src/content_filter.py`
- Фильтровать consumer vs enterprise AI

---

## Ключевые файлы

| Файл | Описание |
|------|----------|
| `src/telegram_bot.py` | Обработка кнопок и модерация |
| `src/moderation.py` | Workflow одобрения |
| `src/rss_parser.py` | Парсинг RSS-источников |
| `src/post_generator.py` | Генерация постов (700-900 символов) |
| `config/rss_feeds.json` | **Список RSS-источников** |
| `config/content_plan.yaml` | Расписание публикаций |

---

## Команды для работы

```bash
# Статус бота
ssh root@141.227.152.143 "systemctl status ai-news-bot"

# Логи в реальном времени
ssh root@141.227.152.143 "journalctl -u ai-news-bot -f"

# Перезапуск
ssh root@141.227.152.143 "systemctl restart ai-news-bot"

# Очистить очередь (если нужно)
ssh root@141.227.152.143 "cd /opt/news-assistant-bot && sqlite3 data/news_bot.db \"DELETE FROM post_queue WHERE status IN ('pending', 'pending_approval');\""
```

---

## Известные ограничения

1. **Telegram caption** = 1024 символа → посты 700-900 символов
2. Рубрики и расписание требуют тестирования перед включением
3. Аналитика не реализована
4. Нет модуля `bs4` на сервере → картинки не скачиваются (установить: `pip install beautifulsoup4`)
