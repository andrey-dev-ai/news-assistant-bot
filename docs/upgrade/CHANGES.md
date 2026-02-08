# Таблица изменений по файлам

## Шаг 1: Конфиг + расписание

| Файл | Что меняется | Детали |
|------|-------------|--------|
| `scheduler.py` | Расписание | 5 публикаций/день → 1 (08:00 генерация, 10:00 публикация) |
| `scheduler.py` | Убран check | `every(5).minutes` → удалено |
| `scheduler.py` | Лог | "Phase 3" → "KLYMO Business Pivot" |
| `src/config.py` | use_rubrics | default `False` → `True` |
| `src/config.py` | use_new_schedule | default `False` → `True` |
| `src/config.py` | Новое поле | `klymo_cta` (env: KLYMO_CTA) |
| `src/rubrics.py` | Enum Rubric | 10 значений → 7 бизнес-рубрик |
| `src/rubrics.py` | RUBRIC_PROMPTS | Все шаблоны переписаны на бизнес-фокус |
| `src/rubrics.py` | Manual рубрики | poll, before_after, fun → удалены |
| `src/rubrics.py` | is_rubric_manual() | Все рубрики auto |
| `config/content_plan.yaml` | Полная перезапись | 7 рубрик, 7 дней, без manual |

## Шаг 2: Промпты

| Файл | Что меняется | Детали |
|------|-------------|--------|
| `config/prompts.yaml` | defaults | channel_name, target_audience |
| `config/prompts.yaml` | relevance | Consumer-фильтр → бизнес-фильтр |
| `config/prompts.yaml` | rubric_prompts | 7 новых шаблонов с CTA |
| `config/prompts.yaml` | image_templates | Пастель → KLYMO dark style |
| `config/prompts.yaml` | Удалено | adapt_english, simplify, telegram_post, quality_check, dalle_prompt |

## Шаг 3: RSS

| Файл | Что меняется | Детали |
|------|-------------|--------|
| `config/rss_feeds.json` | Удалено 12 | Consumer-источники (One Useful Thing, Wired, Guardian, etc.) |
| `config/rss_feeds.json` | Добавлено 7 | Business/enterprise (AWS, Microsoft, Meta, etc.) |
| `config/rss_feeds.json` | Оставлено 9 | TechCrunch, Verge, VentureBeat, OpenAI, Anthropic, etc. |

## Шаг 4: Картинки

| Файл | Что меняется | Детали |
|------|-------------|--------|
| `src/image_generator.py` | KLYMO_VISUAL_STYLE | Новая константа (тёмный + пурпур + циан) |
| `src/image_generator.py` | SCENE_BY_RUBRIC | 7 сцен для рубрик |
| `src/image_generator.py` | generate() | Промпт = style + scene |
| `src/image_generator.py` | choose_image_strategy() | OG-логика убрана, всегда генерируем |

## Шаг 5: Финальная сборка

| Файл | Что меняется | Детали |
|------|-------------|--------|
| `src/post_generator.py` | classify_article() | Новый промпт: бизнес-релевантность |
| `src/post_generator.py` | parse_classifier_response() | Enterprise-фильтр инвертирован |
| `src/post_generator.py` | PostFormat enum | Обновлён под новые рубрики |
| `src/post_generator.py` | _get_universal_prompt() | CEO KLYMO стиль + CTA |
| `src/post_generator.py` | generate_daily_posts() | count=5 → count=1 |
| `src/post_generator.py` | generate_image_prompt() | Пастель → KLYMO dark style |
| `src/telegram_bot.py` | start_command() | Новое приветствие |
| `src/telegram_bot.py` | help_command() | Новое описание |
| `src/telegram_bot.py` | generate_command() | count=5 → count=1 |
| `docs/ARCHITECTURE.md` | Полная перезапись | Всё обновлено под бизнес-фокус |

---

## Файлы НЕ трогаем

| Файл | Почему |
|------|--------|
| `.env` | Конфигурация на сервере, не трогаем |
| `src/database.py` | Структура БД не меняется |
| `src/moderation.py` | Система модерации остаётся |
| `src/post_queue.py` | Схема таблицы подходит (поле `format` уже есть) |
| `src/rss_parser.py` | Парсер универсальный |
| `src/og_parser.py` | Оставляем для метаданных (хоть OG-картинки не используем) |
| `src/deduplicator.py` | Дедупликация работает |
| `src/logger.py` | Логгирование не меняется |
| `src/config_loader.py` | Загрузчик YAML не меняется |
| `src/monitoring.py` | Мониторинг остаётся |
| `src/analytics.py` | Аналитика остаётся |
