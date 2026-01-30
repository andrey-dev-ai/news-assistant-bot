# Инструкция для нового контекста

## Проект: news-assistant-bot

**Канал:** @ai_dlya_doma
**VPS:** 141.227.152.143
**Сервис:** ai-news-bot

---

## Текущий статус (30.01.2026)

✅ Ребрендинг завершён:
- Новый формат постов (1000-1500 символов)
- Ссылки внутри текста
- HTML парсинг работает
- Деплой на VPS выполнен

---

## Быстрые команды

```bash
# Деплой файла на сервер
scp "D:\AI\projects\news-assistant-bot\src\FILE.py" root@141.227.152.143:/opt/news-assistant-bot/src/

# Перезапуск бота
ssh root@141.227.152.143 "systemctl restart ai-news-bot"

# Логи
ssh root@141.227.152.143 "journalctl -u ai-news-bot -f"

# Статус
ssh root@141.227.152.143 "systemctl status ai-news-bot"

# Очистить очередь постов
ssh root@141.227.152.143 "sqlite3 /opt/news-assistant-bot/data/news_bot.db \"DELETE FROM post_queue WHERE status='pending';\""

# Посмотреть посты в очереди
ssh root@141.227.152.143 "sqlite3 /opt/news-assistant-bot/data/news_bot.db \"SELECT id, length(post_text), substr(post_text, 1, 100) FROM post_queue WHERE status='pending';\""
```

---

## Ключевые файлы

| Файл | Что делает |
|------|------------|
| `src/post_generator.py` | Классификация статей + генерация постов |
| `src/telegram_bot.py` | Команды бота (/generate, /preview, /publish_now) |
| `scheduler.py` | Автоматическая публикация по расписанию |
| `.env` | Конфиг (токены, ID канала) |

---

## Важные места в коде

### Промпт генерации постов
`src/post_generator.py:324-381` — метод `_get_universal_prompt()`

### HTML парсинг (критично!)
Везде где отправляется пост должно быть `parse_mode="HTML"`:
- `src/telegram_bot.py:467` — /preview
- `src/telegram_bot.py:529,531` — /publish_now
- `scheduler.py:244,246` — автопубликация

### Количество постов
- `src/telegram_bot.py:399` — `count=5` (ручная генерация)
- `scheduler.py:145` — `count=5` (автогенерация)

---

## Типичные проблемы

### HTML теги показываются как текст
**Причина:** нет `parse_mode="HTML"` при отправке
**Решение:** добавить `parse_mode="HTML"` в вызов send

### Посты старого формата
**Причина:** в очереди остались старые посты
**Решение:** очистить очередь (команда выше)

### Бот не отвечает
```bash
ssh root@141.227.152.143 "journalctl -u ai-news-bot -n 50"
```

---

## Промпт для продолжения работы

```
Работаю с проектом news-assistant-bot.

Путь: d:\AI\projects\news-assistant-bot
VPS: 141.227.152.143
Сервис: ai-news-bot

Прочитай инструкцию: d:\AI\projects\news-assistant-bot\docs\CONTINUE-REBRAND.md

[Опиши задачу]
```
