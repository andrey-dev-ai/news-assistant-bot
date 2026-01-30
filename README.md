# AI News Assistant Bot

Telegram-бот для канала @ai_dlya_mamy — автоматическая генерация постов об AI-инструментах для обычных пользователей.

## Что делает бот

1. **Собирает новости** из 8 RSS-источников (TechCrunch, VentureBeat, The Verge и др.)
2. **Классифицирует** через Claude AI — отбирает релевантные для целевой аудитории (женщины 25-45, не технари)
3. **Генерирует посты** в 3 форматах: AI-находка, Быстрый совет, Промт дня
4. **Публикует в Telegram** по расписанию (09:00, 12:00, 15:00, 18:00, 21:00)

## Статус: Production

Бот работает на VPS-сервере 24/7.

## Команды бота

| Команда | Описание |
|---------|----------|
| `/generate` | Собрать новости и сгенерировать посты |
| `/preview` | Показать готовые посты из очереди |
| `/publish` | Опубликовать следующий пост |
| `/status` | Статус бота и очереди |
| `/help` | Список команд |

## Деплой

**Бот работает на VPS, НЕ локально!**

- **IP:** 141.227.152.143
- **Путь:** `/opt/news-assistant-bot/`
- **Сервис:** `ai-news-bot`

### После изменений в коде:

```bash
# 1. Загрузить файлы
scp "D:\AI\projects\news-assistant-bot\src\<file>.py" root@141.227.152.143:/opt/news-assistant-bot/src/

# 2. Перезапустить
ssh root@141.227.152.143 "systemctl restart ai-news-bot"

# 3. Проверить
ssh root@141.227.152.143 "systemctl status ai-news-bot"

# 4. Закоммитить
git add . && git commit -m "описание" && git push
```

### Логи:
```bash
ssh root@141.227.152.143 "journalctl -u ai-news-bot -f"
```

## Структура

```
news-assistant-bot/
├── scheduler.py              # Точка входа (запускается на сервере)
├── src/
│   ├── post_generator.py     # Классификация и генерация постов
│   ├── telegram_bot.py       # Обработка команд
│   ├── rss_parser.py         # Парсинг RSS
│   ├── post_queue.py         # Очередь постов
│   └── database.py           # SQLite база
├── config/
│   └── rss_feeds.json        # RSS источники
├── data/                     # База данных
└── logs/                     # Логи
```

## Ключевые параметры

| Параметр | Файл | Строка | Значение |
|----------|------|--------|----------|
| Порог классификатора | `src/post_generator.py` | 488 | `>= 45` |
| Модель классификации | `src/post_generator.py` | 146 | `claude-3-haiku` |
| Модель генерации | `src/post_generator.py` | 147 | `claude-sonnet-4` |

## Репозиторий

https://github.com/andrey-dev-ai/news-assistant-bot
