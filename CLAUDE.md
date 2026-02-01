# News Assistant Bot — Project Rules

## КРИТИЧЕСКИ ВАЖНО: Бот работает на VPS!

**Бот НЕ запускается локально — он работает на сервере!**

- **IP:** 141.227.152.143
- **Путь:** `/opt/news-assistant-bot/`
- **Сервис:** `ai-news-bot` (systemd)

### После ЛЮБЫХ изменений в коде:

```bash
# 1. Загрузить файлы
scp "D:\AI\projects\news-assistant-bot\src\*.py" root@141.227.152.143:/opt/news-assistant-bot/src/

# 2. Перезапустить
ssh root@141.227.152.143 "systemctl restart ai-news-bot"

# 3. Проверить логи
ssh root@141.227.152.143 "journalctl -u ai-news-bot --since '2 minutes ago'"

# 4. Закоммитить
git add . && git commit -m "описание" && git push
```

---

## Структура проекта

```
src/
├── post_generator.py   # Генерация постов (Claude)
├── telegram_bot.py     # Обработка команд бота
├── moderation.py       # Система одобрения
├── image_generator.py  # GPT Image 1
├── rubrics.py          # 10 рубрик
└── ...

config/
├── rss_feeds.json      # 21 RSS источник
├── content_plan.yaml   # Недельное расписание
└── prompts.yaml        # Промпты
```

---

## Документация

| Файл | Описание |
|------|----------|
| `docs/STATUS.md` | **Текущий статус и TODO** |
| `docs/ARCHITECTURE.md` | Техническая документация |
| `docs/content_strategy.md` | Контент-стратегия |
| `docs/monetization.md` | Монетизация |

---

## Текущая конфигурация

```bash
USE_MODERATION=true      # Ручное одобрение постов
USE_RUBRICS=false        # Рубрики (готово, не включено)
USE_NEW_SCHEDULE=false   # Недельное расписание (готово, не включено)
```

---

## Ключевые параметры

- **Длина поста:** 700-900 символов (Telegram caption = 1024)
- **Порог классификатора:** `confidence >= 45`
- **Модели:** Claude Haiku (классификация), Claude Sonnet (генерация)
- **Картинки:** GPT Image 1 (soft 3D стиль)

---

## Команды управления

```bash
# Статус
ssh root@141.227.152.143 "systemctl status ai-news-bot"

# Логи
ssh root@141.227.152.143 "journalctl -u ai-news-bot -f"

# Перезапуск
ssh root@141.227.152.143 "systemctl restart ai-news-bot"

# Очистить очередь
ssh root@141.227.152.143 "sqlite3 /opt/news-assistant-bot/data/news_bot.db \"DELETE FROM post_queue WHERE status IN ('pending', 'pending_approval');\""
```
