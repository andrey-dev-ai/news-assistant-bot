# План апгрейда — 5 шагов

## Порядок выполнения

```
Шаг 1 (конфиг + расписание) → деплой → проверка
  ↓
Шаг 2 (промпты) → деплой → проверка
  ↓
Шаг 3 (RSS) → проверка URL → деплой
  ↓
Шаг 4 (картинки) → деплой → проверка
  ↓
Шаг 5 (финальная сборка) → деплой → тест /generate
```

---

## Шаг 1: Конфиг + расписание + рубрики

**Файлы:** `scheduler.py`, `src/config.py`, `src/rubrics.py`, `config/content_plan.yaml`

### scheduler.py
- Расписание: 5 постов/день → 1 пост/день
- `08:00` → `generate_daily_posts()` — генерация 1 поста
- `10:00` → `publish_scheduled_post()` — публикация
- Убрать `every(5).minutes` check
- Лог: "Phase 3" → "KLYMO Business Pivot"

### config.py
- `use_rubrics` default: `False` → `True`
- `use_new_schedule` default: `False` → `True`
- Новое поле: `klymo_cta` (default: "🤖 Автоматизация для бизнеса → @klymo_tech")

### rubrics.py
- Enum `Rubric` → 7 бизнес-рубрик (вместо 10):
  1. `AI_NEWS = "ai_news"` — 🔥 AI-новость
  2. `TOOL_REVIEW = "tool_review"` — 🛠 Инструмент дня
  3. `CASE_STUDY = "case_study"` — 💰 Кейс автоматизации
  4. `AI_VS_MANUAL = "ai_vs_manual"` — 📊 AI vs ручная работа
  5. `BUSINESS_PROMPT = "business_prompt"` — 🎯 Промпт для бизнеса
  6. `AI_EXPLAINER = "ai_explainer"` — 🧠 AI-ликбез
  7. `WEEKLY_DIGEST = "weekly_digest"` — ⚡ Дайджест недели
- `RUBRIC_PROMPTS` — все с бизнес-фокусом + CTA на @klymo_tech
- Убраны manual рубрики (poll, before_after, fun)

### content_plan.yaml
- 7 постов/неделю (1/день), все auto
- Расписание: Пн ai_news, Вт tool_review, Ср case_study, Чт ai_vs_manual, Пт business_prompt, Сб ai_explainer, Вс weekly_digest

---

## Шаг 2: Промпты

**Файл:** `config/prompts.yaml` — полная перезапись

- `defaults`: channel_name "AI для бизнеса", target_audience "Предприниматели, SMB"
- `relevance`: классификатор → бизнес-релевантность (enterprise = relevant, consumer = filtered)
- 7 рубрик-шаблонов с CTA, тон CEO, макс 1500 символов
- `image_templates`: KLYMO visual style (тёмный фон, пурпурные градиенты, циановые акценты)
- Удалены неиспользуемые секции (adapt_english, simplify, telegram_post, quality_check, dalle_prompt)

---

## Шаг 3: RSS-источники

**Файл:** `config/rss_feeds.json`

**Оставить (9):** TechCrunch AI, The Verge AI, VentureBeat AI, OpenAI Blog, Anthropic News, Google AI Blog, Hugging Face Blog, THE DECODER, AI News

**Добавить (7):** AWS ML Blog, Microsoft AI Blog, Meta AI Blog, DeepLearning.AI, MarkTechPost, Hacker News, Synced Review

**Удалить (12):** One Useful Thing, The Rundown AI, ZDNET AI, Futurism AI, Synthedia, Last Week in AI, Wired AI, The Guardian AI, Ars Technica AI, Habr ML, Product Hunt, MIT Tech Review

**Перед применением:** проверка доступности каждого URL через curl

---

## Шаг 4: Генератор картинок

**Файл:** `src/image_generator.py`

- Константа `KLYMO_VISUAL_STYLE`: тёмный фон (#0D0D1A), пурпурные градиенты (#6B2FA0→#9B59B6), циановые акценты (#00D4FF), абстрактная геометрия, NO text/humans/faces
- `SCENE_BY_RUBRIC`: 7 сцен для каждой рубрики
- `generate()`: промпт = KLYMO_VISUAL_STYLE + SCENE_BY_RUBRIC[category]
- `choose_image_strategy()`: всегда генерируем (OG-логика убрана)

---

## Шаг 5: Финальная сборка

**Файлы:** `src/post_generator.py`, `src/telegram_bot.py`, `docs/ARCHITECTURE.md`

### post_generator.py
- `classify_article()`: новый промпт — бизнес-релевантность
- Инвертирован фильтр: enterprise/business → pass, consumer → filtered
- `PostFormat` обновлён под новые рубрики
- `_get_universal_prompt()`: CEO KLYMO стиль, CTA
- `generate_daily_posts()`: count=5 → count=1

### telegram_bot.py
- `/start`: "KLYMO AI Bot — автоматизация для бизнеса"
- `/help`: обновлённое описание
- `/generate`: генерирует 1 пост (не 5)

### ARCHITECTURE.md
- Полное обновление: описание, ЦА, рубрики, расписание, визуал, RSS, экономика

---

## Деплой (после каждого шага)

```bash
scp "D:\AI\projects\news-assistant-bot\src\*.py" root@141.227.152.143:/opt/news-assistant-bot/src/
scp "D:\AI\projects\news-assistant-bot\config\*" root@141.227.152.143:/opt/news-assistant-bot/config/
scp "D:\AI\projects\news-assistant-bot\scheduler.py" root@141.227.152.143:/opt/news-assistant-bot/
ssh root@141.227.152.143 "systemctl restart ai-news-bot"
ssh root@141.227.152.143 "journalctl -u ai-news-bot --since '1 minute ago'"
```

## Верификация (финальная)

1. `/generate` → 1 пост с бизнес-фокусом
2. CTA → @klymo_tech
3. Картинка: тёмный фон, пурпурные градиенты
4. Логи: `journalctl -u ai-news-bot -f`
