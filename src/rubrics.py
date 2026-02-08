"""Rubric system for Phase 3: content categories and weekly schedule."""

from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from logger import get_logger

logger = get_logger("news_bot.rubrics")


class Rubric(Enum):
    """Content rubrics for the channel (KLYMO Business Pivot)."""
    AI_NEWS = "ai_news"                # 🔥 AI-новость
    TOOL_REVIEW = "tool_review"        # 🛠 Инструмент дня
    CASE_STUDY = "case_study"          # 💰 Кейс автоматизации
    AI_VS_MANUAL = "ai_vs_manual"      # 📊 AI vs ручная работа
    BUSINESS_PROMPT = "business_prompt" # 🎯 Промпт для бизнеса
    AI_EXPLAINER = "ai_explainer"      # 🧠 AI-ликбез
    WEEKLY_DIGEST = "weekly_digest"    # ⚡ Дайджест недели


# Mapping from rubric to prompt style (v5: Frameworks + Hooks + Engagement)
RUBRIC_PROMPTS = {
    Rubric.AI_NEWS: """
ФРЕЙМВОРК PAS (Problem → Agitate → Solve):
🔥 <b>[ХУК — проблема или шок-факт]</b>

[Problem: Что случилось — 2-3 предложения. Конкретика, цифры.]

[Agitate: Почему бизнесу нельзя игнорировать — 2-3 предложения.]

[Solve: Обрыв — интрига → кнопка «Далі».]

👇 А вы уже это используете?

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-800 символов. БЕЗ линий. БЕЗ ссылок. Хук <b>жирным</b>.
""",

    Rubric.TOOL_REVIEW: """
ФРЕЙМВОРК AIDA (Attention → Interest → Desire → Action):
🛠 <b>[ХУК — что делает + вау-факт / экономия]</b>

[Interest: Какую боль решает — 2-3 предложения. Сценарий из жизни.]

[Desire: Ключевой результат — 2-3 предложения. Цифры, скорость.]

[Action: Обрыв — цена/интрига → кнопка «Далі».]

👇 Пользуетесь чем-то подобным?

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-800 символов. БЕЗ линий. Результат > фичи. Хук <b>жирным</b>.
""",

    Rubric.CASE_STUDY: """
ФРЕЙМВОРК STAR (Situation → Task → Action → Result):
💰 <b>[ХУК — Result первым: "Було X → Стало Y" с цифрами]</b>

[Situation: Боль / хаос — 2-3 предложения. Узнаваемая ситуация.]

[Task + Action: Что внедрили — 2-3 предложения.]

[Result: Обрыв — самый вкусный результат / интрига.]

👇 Какой процесс автоматизировали бы первым?

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-800 символов. БЕЗ линий. Цифры ОБЯЗАТЕЛЬНЫ. Хук <b>жирным</b>.
""",

    Rubric.AI_VS_MANUAL: """
ФРЕЙМВОРК Before/After:
📊 <b>[ХУК — драматичный контраст в одну строку]</b>

[Контекст задачи — 1-2 предложения.]

❌ Вручну: [время, стоимость, боль]
✅ З AI: [время, стоимость, кайф]

[Вывод / провокация — 1-2 предложения.]

👇 Считали, сколько стоит ручная работа в команде?

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-800 символов. Контраст ❌/✅ — ядро. Цифры в обоих. Хук <b>жирным</b>.
""",

    Rubric.BUSINESS_PROMPT: """
ФРЕЙМВОРК Problem → Prompt → Result:
🎯 <b>[ХУК — какую боль убирает этот промпт]</b>

[Problem: Задача + контекст — 2-3 предложения.]

<code>[Готовый промпт — 2-4 строки, можно скопировать]</code>

[Result: Что получите — 1-2 предложения.]

👇 Скопировали? Делитесь результатом!

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-900 символов. Промпт в <code>. Промпт РАБОЧИЙ. Хук <b>жирным</b>.
""",

    Rubric.AI_EXPLAINER: """
ФРЕЙМВОРК «Простая аналогия» (Термин → Аналогия → Бизнес):
🧠 <b>[ХУК — вопрос или неожиданная аналогия]</b>

[Аналогия из жизни — 2-3 предложения. Как для 10-летнего.]

[Бизнес-применение — 2-3 предложения.]

[Интрига — 1 предложение.]

👇 Что объяснить следующим?

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-800 символов. Аналогия ОБЯЗАТЕЛЬНА. 1 концепция = 1 пост. Хук <b>жирным</b>.
""",

    Rubric.WEEKLY_DIGEST: """
ФРЕЙМВОРК «Топ-3 + Инсайт»:
⚡ <b>[ХУК — главная мысль недели, провокационно]</b>

1️⃣ [Новость 1 — 1-2 предложения]
2️⃣ [Новость 2 — 1-2 предложения]
3️⃣ [Новость 3 — 1-2 предложения]

[ИНСАЙТ — неочевидный вывод, объединяющий все 3.]

👇 Что пропустили на этой неделе?

🤖 Тільки важливе про AI → @klymo_tech

ПРАВИЛА: 500-900 символов. Ровно 3 новости. ИНСАЙТ обязателен. Хук <b>жирным</b>.
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
                "monday": [{"time": "10:00", "rubric": "ai_news"}],
                "tuesday": [{"time": "10:00", "rubric": "tool_review"}],
                "wednesday": [{"time": "10:00", "rubric": "case_study"}],
                "thursday": [{"time": "10:00", "rubric": "ai_vs_manual"}],
                "friday": [{"time": "10:00", "rubric": "business_prompt"}],
                "saturday": [{"time": "10:00", "rubric": "ai_explainer"}],
                "sunday": [{"time": "10:00", "rubric": "weekly_digest"}],
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
        return False  # All rubrics are auto-generated now

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
