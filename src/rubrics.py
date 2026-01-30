"""Rubric system for Phase 3: content categories and weekly schedule."""

from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from logger import get_logger

logger = get_logger("news_bot.rubrics")


class Rubric(Enum):
    """Content rubrics for the channel."""
    TOOL_REVIEW = "tool_review"       # AI-инструмент недели
    NEWS = "news"                      # Новости нейросетей
    PROMPT_HOME = "prompt_home"        # Промпт для дома
    LIFEHACK = "lifehack"              # Лайфхак с AI
    FREE_SERVICE = "free_service"      # Бесплатный сервис
    COLLECTION = "collection"          # Подборка недели
    DIGEST = "digest"                  # Дайджест недели
    POLL = "poll"                      # Опрос (ручной)
    BEFORE_AFTER = "before_after"      # До/После (ручной)
    FUN = "fun"                        # Мем/Fun (ручной)


# Mapping from rubric to prompt style
RUBRIC_PROMPTS = {
    Rubric.TOOL_REVIEW: """
Создай пост для рубрики "AI-инструмент недели".

ФОРМАТ:
🛠 <b>[Название инструмента]</b>

Первый абзац — что это за инструмент и для чего. Простым языком, без технических терминов.

Второй абзац — как использовать дома. Конкретный пример из жизни: "Например, можно..."

Третий абзац — ключевые особенности:
• Бесплатно/платно
• Работает на русском или нет
• Нужна ли регистрация

<a href="URL">Попробовать →</a>

#инструмент_недели
""",

    Rubric.NEWS: """
Создай пост для рубрики "Новости нейросетей".

ФОРМАТ:
📰 <b>[Заголовок новости]</b>

Первый абзац — суть новости. Что произошло, кто выпустил, что изменилось.

Второй абзац — почему это важно для обычного пользователя. Как это повлияет на повседневное использование AI.

Третий абзац (опционально) — контекст или мнение экспертов.

<a href="URL">Подробнее</a>

#новости
""",

    Rubric.PROMPT_HOME: """
Создай пост для рубрики "Промпт для дома".

ФОРМАТ:
💡 <b>Промпт дня: [тема]</b>

Описание задачи — какую проблему решает этот промпт (1-2 предложения).

<b>Промпт:</b>
<code>
[Готовый промпт для копирования]
</code>

<b>Пример результата:</b>
[Краткий пример того, что получится]

💡 Совет: [маленький лайфхак по использованию]

#промпт_дня
""",

    Rubric.LIFEHACK: """
Создай пост для рубрики "Лайфхак с AI".

ФОРМАТ:
✨ <b>[Название лайфхака]</b>

<b>Проблема:</b> [что хотим решить]

<b>Решение:</b>
1. [Шаг 1]
2. [Шаг 2]
3. [Шаг 3]

<b>Результат:</b> [что получим, сколько времени сэкономим]

#лайфхак
""",

    Rubric.FREE_SERVICE: """
Создай пост для рубрики "Бесплатный сервис".

ФОРМАТ:
🆓 <b>[Название сервиса] — бесплатно!</b>

Что умеет:
• [Функция 1]
• [Функция 2]
• [Функция 3]

Кому подойдёт: [целевая аудитория]

Ограничения бесплатной версии: [если есть]

<a href="URL">Попробовать бесплатно →</a>

#бесплатно
""",

    Rubric.COLLECTION: """
Создай пост для рубрики "Подборка недели".

ФОРМАТ:
📚 <b>Подборка: [тема]</b>

1. <b>[Название 1]</b> — [краткое описание]
   <a href="URL">Ссылка</a>

2. <b>[Название 2]</b> — [краткое описание]
   <a href="URL">Ссылка</a>

3. <b>[Название 3]</b> — [краткое описание]
   <a href="URL">Ссылка</a>

💬 Какой попробуете первым?

#подборка
""",

    Rubric.DIGEST: """
Создай пост для рубрики "Дайджест недели".

ФОРМАТ:
📋 <b>Дайджест недели: [даты]</b>

<b>Главное:</b>
• [Ключевая новость 1]
• [Ключевая новость 2]

<b>Новые инструменты:</b>
• [Инструмент 1]
• [Инструмент 2]

<b>Полезное из нашего канала:</b>
• [Ссылка на пост 1]
• [Ссылка на пост 2]

До встречи на следующей неделе! 👋

#дайджест
""",
}


class RubricManager:
    """Manages rubrics and weekly content schedule."""

    def __init__(self, config_path: str = "config/content_plan.yaml"):
        """Initialize rubric manager."""
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load content plan configuration."""
        if not self.config_path.exists():
            logger.warning(f"Content plan not found: {self.config_path}")
            return self._get_default_config()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading content plan: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Return default configuration if file not found."""
        return {
            "schedule": {
                "monday": [
                    {"time": "10:00", "rubric": "tool_review"},
                    {"time": "19:00", "rubric": "poll", "manual": True},
                ],
                "tuesday": [
                    {"time": "12:00", "rubric": "news"},
                    {"time": "20:00", "rubric": "prompt_home"},
                ],
                "wednesday": [
                    {"time": "11:00", "rubric": "lifehack"},
                    {"time": "21:00", "rubric": "before_after", "manual": True},
                ],
                "thursday": [
                    {"time": "10:00", "rubric": "news"},
                    {"time": "19:00", "rubric": "free_service"},
                ],
                "friday": [
                    {"time": "12:00", "rubric": "collection"},
                ],
                "saturday": [
                    {"time": "15:00", "rubric": "fun", "manual": True},
                ],
                "sunday": [
                    {"time": "21:00", "rubric": "digest"},
                ],
            },
            "rubrics": {},
        }

    def get_rubric_for_slot(self, day: str, time: str) -> Optional[Rubric]:
        """
        Get rubric for a specific day and time slot.

        Args:
            day: Day of week (monday, tuesday, etc.)
            time: Time in HH:MM format

        Returns:
            Rubric enum or None
        """
        schedule = self.config.get("schedule", {})
        day_schedule = schedule.get(day.lower(), [])

        for slot in day_schedule:
            if slot.get("time") == time:
                rubric_name = slot.get("rubric")
                try:
                    return Rubric(rubric_name)
                except ValueError:
                    logger.warning(f"Unknown rubric: {rubric_name}")
                    return None

        return None

    def get_prompt_for_rubric(self, rubric: Rubric) -> str:
        """
        Get generation prompt template for a rubric.

        Args:
            rubric: Rubric enum

        Returns:
            Prompt template string
        """
        return RUBRIC_PROMPTS.get(rubric, "")

    def get_slots_for_week(self) -> List[Dict]:
        """
        Get all content slots for the current week.

        Returns:
            List of slots with day, time, rubric, and manual flag
        """
        schedule = self.config.get("schedule", {})
        slots = []

        # Order days starting from Monday
        day_order = ["monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"]

        for day in day_order:
            day_schedule = schedule.get(day, [])
            for slot in day_schedule:
                slots.append({
                    "day": day,
                    "time": slot.get("time"),
                    "rubric": slot.get("rubric"),
                    "manual": slot.get("manual", False),
                    "hashtag": self._get_hashtag(slot.get("rubric")),
                })

        return slots

    def get_auto_slots_for_week(self) -> List[Dict]:
        """Get only auto-generated slots (not manual)."""
        return [s for s in self.get_slots_for_week() if not s.get("manual")]

    def get_manual_slots_for_week(self) -> List[Dict]:
        """Get only manual content slots."""
        return [s for s in self.get_slots_for_week() if s.get("manual")]

    def _get_hashtag(self, rubric_name: str) -> Optional[str]:
        """Get hashtag for a rubric."""
        rubrics_config = self.config.get("rubrics", {})
        rubric_config = rubrics_config.get(rubric_name, {})
        return rubric_config.get("hashtag")

    def get_next_slot(self) -> Optional[Dict]:
        """
        Get the next upcoming content slot.

        Returns:
            Next slot dict or None
        """
        now = datetime.now()
        current_day = now.strftime("%A").lower()
        current_time = now.strftime("%H:%M")

        # Days in order starting from today
        day_order = ["monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"]
        today_idx = day_order.index(current_day)
        ordered_days = day_order[today_idx:] + day_order[:today_idx]

        schedule = self.config.get("schedule", {})

        for i, day in enumerate(ordered_days):
            day_schedule = schedule.get(day, [])
            for slot in sorted(day_schedule, key=lambda s: s.get("time", "")):
                slot_time = slot.get("time", "00:00")

                # For today, only consider future slots
                if i == 0 and slot_time <= current_time:
                    continue

                return {
                    "day": day,
                    "time": slot_time,
                    "rubric": slot.get("rubric"),
                    "manual": slot.get("manual", False),
                    "days_ahead": i,
                }

        return None

    def get_reminder_for_manual_slot(self, rubric_name: str) -> Optional[str]:
        """
        Get reminder message for manual content creation.

        Args:
            rubric_name: Name of the rubric

        Returns:
            Reminder message or None
        """
        reminders = self.config.get("manual_reminders", {})
        reminder_config = reminders.get(rubric_name, {})
        return reminder_config.get("message")

    def is_rubric_manual(self, rubric: Rubric) -> bool:
        """Check if rubric requires manual content creation."""
        return rubric in [Rubric.POLL, Rubric.BEFORE_AFTER, Rubric.FUN]

    def get_rubric_info(self, rubric: Rubric) -> Dict:
        """Get full info about a rubric."""
        rubrics_config = self.config.get("rubrics", {})
        rubric_config = rubrics_config.get(rubric.value, {})

        return {
            "name": rubric_config.get("name", rubric.value),
            "emoji": rubric_config.get("emoji", "📝"),
            "hashtag": rubric_config.get("hashtag"),
            "description": rubric_config.get("description", ""),
            "auto_generate": rubric_config.get("auto_generate", True),
        }


# Singleton instance
_rubric_manager: Optional[RubricManager] = None


def get_rubric_manager() -> RubricManager:
    """Get or create rubric manager singleton."""
    global _rubric_manager
    if _rubric_manager is None:
        _rubric_manager = RubricManager()
    return _rubric_manager


if __name__ == "__main__":
    # Test the rubric manager
    rm = RubricManager()

    print("All slots for the week:")
    for slot in rm.get_slots_for_week():
        print(f"  {slot['day']} {slot['time']}: {slot['rubric']} "
              f"{'(manual)' if slot['manual'] else ''}")

    print(f"\nNext slot: {rm.get_next_slot()}")

    print("\nAuto-generated slots:")
    for slot in rm.get_auto_slots_for_week():
        print(f"  {slot['day']} {slot['time']}: {slot['rubric']}")

    print("\nManual slots:")
    for slot in rm.get_manual_slots_for_week():
        print(f"  {slot['day']} {slot['time']}: {slot['rubric']}")
