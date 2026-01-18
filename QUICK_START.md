# Быстрый старт - AI News Bot

## Что нужно сделать прямо сейчас:

### 1. Получить ключи (10 минут)

#### Claude API Key
- Идите: https://console.anthropic.com/
- Регистрация → API Keys → Create Key
- Скопируйте ключ

#### Telegram Bot
- Откройте Telegram → @BotFather
- Команда: `/newbot`
- Придумайте имя и username
- Скопируйте токен

#### Ваш Telegram ID
- Откройте Telegram → @userinfobot
- Нажмите Start
- Скопируйте число (ваш ID)

### 2. Установить зависимости

Откройте командную строку в папке проекта:

```bash
cd D:\AI\news-assistant-bot
pip install -r requirements.txt
```

### 3. Настроить .env

Скопируйте `.env.example` в `.env`:

```bash
copy .env.example .env
```

Откройте `.env` блокнотом и вставьте ваши ключи:

```
ANTHROPIC_API_KEY=ваш_ключ_claude
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_USER_ID=ваш_id
DIGEST_TIMES=09:00,18:00
```

### 4. Первый запуск (тест)

```bash
python main.py
```

Должно прийти сообщение в Telegram!

### 5. Автоматическая работа

Для постоянной работы по расписанию:

```bash
python scheduler.py
```

Оставьте окно открытым или сверните.

## Готово!

Бот будет отправлять вам дайджесты AI-новостей каждый день в 09:00 и 18:00.

## Проблемы?

1. Проверьте `.env` - все ключи правильно скопированы?
2. Нажали Start у бота в Telegram?
3. Все библиотеки установлены? (`pip install -r requirements.txt`)

## Полная документация

Читайте [README.md](README.md) для подробностей.
