"""Monitoring and metrics for @ai_dlya_doma bot."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from database import Database
from deduplicator import get_deduplicator
from logger import get_logger

logger = get_logger("news_bot.monitoring")


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: str  # ok, warning, critical
    value: any
    threshold: Optional[any] = None
    message: Optional[str] = None


class BotMonitor:
    """Monitor bot health and performance metrics."""

    # Alert thresholds
    BUFFER_CRITICAL = 5
    BUFFER_WARNING = 10
    ERROR_RATE_THRESHOLD = 5  # percent
    REJECTION_RATE_THRESHOLD = 85  # percent

    def __init__(self, db: Optional[Database] = None):
        """Initialize monitor."""
        self.db = db or Database()

    def get_all_metrics(self) -> Dict:
        """Get all metrics for dashboard."""
        return {
            "timestamp": datetime.now().isoformat(),
            "database": self.db.get_stats(),
            "queue_health": self.db.get_queue_health(),
            "daily_summary": self.db.get_daily_summary(days=7),
            "deduplicator": get_deduplicator().get_stats(),
            "health_checks": self.run_health_checks(),
        }

    def run_health_checks(self) -> List[Dict]:
        """Run all health checks and return results."""
        checks = [
            self._check_buffer_health(),
            self._check_rejection_rate(),
            self._check_daily_output(),
        ]
        return [
            {
                "name": c.name,
                "status": c.status,
                "value": c.value,
                "threshold": c.threshold,
                "message": c.message,
            }
            for c in checks
        ]

    def _check_buffer_health(self) -> HealthCheckResult:
        """Check if post buffer has enough content."""
        queue_health = self.db.get_queue_health()
        count = queue_health["posts_in_buffer"]

        if count < self.BUFFER_CRITICAL:
            return HealthCheckResult(
                name="buffer_health",
                status="critical",
                value=count,
                threshold=self.BUFFER_CRITICAL,
                message=f"В буфере осталось {count} постов! Проверь источники.",
            )
        elif count < self.BUFFER_WARNING:
            return HealthCheckResult(
                name="buffer_health",
                status="warning",
                value=count,
                threshold=self.BUFFER_WARNING,
                message=f"В буфере {count} постов, скоро закончатся.",
            )
        else:
            return HealthCheckResult(
                name="buffer_health",
                status="ok",
                value=count,
                threshold=self.BUFFER_WARNING,
            )

    def _check_rejection_rate(self) -> HealthCheckResult:
        """Check if rejection rate is too high."""
        summary = self.db.get_daily_summary(days=1)
        if not summary:
            return HealthCheckResult(
                name="rejection_rate",
                status="ok",
                value=0,
                threshold=self.REJECTION_RATE_THRESHOLD,
            )

        today = summary[0]
        total = today.get("total", 0)
        rejected = today.get("rejected", 0)

        if total == 0:
            rate = 0
        else:
            rate = round((rejected / total) * 100, 1)

        if rate > self.REJECTION_RATE_THRESHOLD:
            return HealthCheckResult(
                name="rejection_rate",
                status="critical",
                value=rate,
                threshold=self.REJECTION_RATE_THRESHOLD,
                message=f"{rate}% контента отклонено за 24ч. Проверь настройки фильтра.",
            )
        else:
            return HealthCheckResult(
                name="rejection_rate",
                status="ok",
                value=rate,
                threshold=self.REJECTION_RATE_THRESHOLD,
            )

    def _check_daily_output(self) -> HealthCheckResult:
        """Check if we're publishing enough content."""
        stats = self.db.get_stats()
        today_count = stats.get("today_published", 0)
        target = 5  # 5 posts per day target

        if today_count == 0:
            return HealthCheckResult(
                name="daily_output",
                status="warning",
                value=today_count,
                threshold=target,
                message="Сегодня еще не было публикаций.",
            )
        elif today_count < target:
            return HealthCheckResult(
                name="daily_output",
                status="ok",
                value=today_count,
                threshold=target,
                message=f"Опубликовано {today_count}/{target} постов.",
            )
        else:
            return HealthCheckResult(
                name="daily_output",
                status="ok",
                value=today_count,
                threshold=target,
            )

    def get_alerts(self) -> List[str]:
        """Get list of active alerts as formatted messages."""
        alerts = []
        for check in self.run_health_checks():
            if check["status"] in ("warning", "critical"):
                emoji = "🔴" if check["status"] == "critical" else "🟡"
                alerts.append(f"{emoji} {check['message']}")
        return alerts

    def format_stats_message(self) -> str:
        """Format stats for Telegram message."""
        stats = self.db.get_stats()
        queue = self.db.get_queue_health()
        dedup = get_deduplicator().get_stats()

        # Health status emoji
        health_emoji = {"ok": "🟢", "warning": "🟡", "critical": "🔴"}
        queue_status = health_emoji.get(queue["health_status"], "⚪")

        # Format categories
        categories = stats.get("categories_7d", {})
        cat_lines = "\n".join(
            f"  • {cat}: {count}" for cat, count in sorted(categories.items())
        )
        if not cat_lines:
            cat_lines = "  Нет данных"

        msg = f"""📊 *Статистика бота*

*Публикации:*
• Всего: {stats['total_articles']}
• Сегодня: {stats['today_published']}
• Последняя: {stats['last_sent'] or 'Нет'}

*Очередь:* {queue_status}
• В буфере: {queue['posts_in_buffer']} постов
• Следующий: {queue['next_post'] or 'Не запланирован'}

*Дедупликация:*
• Отслеживается URL: {dedup['unique_urls']}
• Отслеживается заголовков: {dedup['tracked_titles']}
• Порог схожести: {dedup['similarity_threshold']}

*Категории (7 дней):*
{cat_lines}
"""
        # Add alerts if any
        alerts = self.get_alerts()
        if alerts:
            msg += "\n*Предупреждения:*\n" + "\n".join(alerts)

        return msg

    def format_daily_report(self) -> str:
        """Format daily report for Telegram."""
        summary = self.db.get_daily_summary(days=7)
        if not summary:
            return "📈 *Отчёт за неделю*\n\nНет данных."

        lines = ["📈 *Отчёт за неделю*\n"]
        for day in summary:
            date = day["day"]
            total = day["total"]
            published = day["published"]
            rejected = day["rejected"]
            avg_rel = day["avg_relevance"] or 0

            rate = round((published / total) * 100) if total > 0 else 0
            lines.append(f"• {date}: {published}/{total} ({rate}%) rel:{avg_rel}")

        return "\n".join(lines)


# Singleton instance
_monitor: Optional[BotMonitor] = None


def get_monitor() -> BotMonitor:
    """Get or create global monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = BotMonitor()
    return _monitor


if __name__ == "__main__":
    # Test monitoring
    monitor = BotMonitor()

    print("=" * 50)
    print("Bot Monitoring Test")
    print("=" * 50)

    metrics = monitor.get_all_metrics()
    print(f"\nMetrics: {metrics}")

    print("\n" + "-" * 50)
    print("Stats Message:")
    print(monitor.format_stats_message())

    print("\n" + "-" * 50)
    print("Daily Report:")
    print(monitor.format_daily_report())

    print("\n" + "-" * 50)
    print("Alerts:")
    for alert in monitor.get_alerts():
        print(alert)
