# News Assistant Bot — Project Rules

## КРИТИЧЕСКИ ВАЖНО: Бот работает на VPS!

**Бот НЕ запускается локально — он работает на сервере!**

### Сервер
- **IP:** 141.227.152.143
- **Путь:** `/opt/news-assistant-bot/`
- **Сервис:** `ai-news-bot` (systemd)
- **SSH:** `ssh root@141.227.152.143` (пароль в credentials.md)

### После ЛЮБЫХ изменений в коде:

1. **Загрузить файлы на сервер:**
```bash
scp "D:\AI\projects\news-assistant-bot\src\<file>.py" root@141.227.152.143:/opt/news-assistant-bot/src/
scp "D:\AI\projects\news-assistant-bot\config\rss_feeds.json" root@141.227.152.143:/opt/news-assistant-bot/config/
```

2. **Перезапустить сервис:**
```bash
ssh root@141.227.152.143 "systemctl restart ai-news-bot"
```

3. **Проверить статус:**
```bash
ssh root@141.227.152.143 "systemctl status ai-news-bot"
```

4. **Закоммитить и запушить на GitHub:**
```bash
cd D:\AI\projects\news-assistant-bot
git add .
git commit -m "описание изменений"
git push
```

### Логи на сервере
```bash
ssh root@141.227.152.143 "journalctl -u ai-news-bot -f"
```

### Тестирование
После деплоя — `/generate` в Telegram боте (@ai_dlya_doma_bot)

---

## Структура проекта

```
src/
├── post_generator.py   # Классификация и генерация постов
├── telegram_bot.py     # Обработка команд бота
├── rss_parser.py       # Парсинг RSS
├── database.py         # База данных
└── ...

config/
└── rss_feeds.json      # RSS источники
```

## Ключевые параметры

- **Порог классификатора:** `src/post_generator.py:488` — `confidence >= 45`
- **RSS источники:** `config/rss_feeds.json`
