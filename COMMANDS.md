# Команды для работы с ботом

## Установка

```bash
# Перейти в папку проекта
cd D:\AI\news-assistant-bot

# Установить все библиотеки
pip install -r requirements.txt
```

## Настройка

```bash
# Скопировать пример конфига
copy .env.example .env

# Открыть .env в блокноте для редактирования
notepad .env
```

## Запуск

```bash
# Разовый запуск (для теста)
python main.py

# Постоянная работа по расписанию
python scheduler.py
```

## Тестирование модулей

```bash
# Проверить парсинг RSS
python src/rss_parser.py

# Проверить обработку AI (требует ANTHROPIC_API_KEY)
python src/ai_processor.py

# Проверить отправку в Telegram (требует токен и ID)
python src/telegram_bot.py

# Проверить базу данных
python src/database.py
```

## Остановка

```
Ctrl + C (в окне терминала где запущен scheduler.py)
```

## Проверка логов

```bash
# Посмотреть что происходит в консоли
# Логи выводятся прямо в окно терминала
```

## Обновление источников

```bash
# Открыть файл с RSS-фидами
notepad config\rss_feeds.json
```

## Изменение расписания

```bash
# Открыть .env и изменить DIGEST_TIMES
notepad .env

# Пример:
# DIGEST_TIMES=08:00,20:00  (два раза в день)
# DIGEST_TIMES=12:00         (один раз в день)
```

## Полезные ссылки

- Claude API: https://console.anthropic.com/
- Создать Telegram бота: @BotFather
- Узнать свой Telegram ID: @userinfobot
