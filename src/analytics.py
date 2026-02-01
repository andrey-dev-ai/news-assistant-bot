"""Analytics module for tracking post performance."""

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from logger import get_logger

logger = get_logger("news_bot.analytics")


class Analytics:
    """Track and analyze post performance metrics."""

    def __init__(self, db_path: str = "data/news_bot.db"):
        """Initialize analytics module."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _init_tables(self):
        """Create analytics tables if not exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Post stats table - metrics per post
            conn.execute("""
                CREATE TABLE IF NOT EXISTS post_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    message_id INTEGER,
                    channel_id TEXT,
                    views INTEGER DEFAULT 0,
                    forwards INTEGER DEFAULT 0,
                    reactions INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    clicks INTEGER DEFAULT 0,
                    ab_group TEXT DEFAULT 'A',
                    published_at DATETIME,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(post_id)
                )
            """)
            # Migration: add ab_group column if not exists
            try:
                conn.execute("ALTER TABLE post_stats ADD COLUMN ab_group TEXT DEFAULT 'A'")
            except sqlite3.OperationalError:
                pass  # Column already exists
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_post_stats_message
                ON post_stats(message_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_post_stats_published
                ON post_stats(published_at)
            """)

            # Daily metrics table - aggregated daily stats
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    posts_published INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0,
                    total_forwards INTEGER DEFAULT 0,
                    total_reactions INTEGER DEFAULT 0,
                    avg_err REAL DEFAULT 0,
                    subscribers INTEGER DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_metrics_date
                ON daily_metrics(date)
            """)

            conn.commit()
            logger.info("Analytics tables initialized")

    def record_publication(
        self,
        post_id: int,
        message_id: int,
        channel_id: str,
        published_at: datetime = None,
        ab_group: str = None,
    ) -> bool:
        """
        Record a post publication for tracking.

        Args:
            post_id: Internal post queue ID
            message_id: Telegram message ID in channel
            channel_id: Telegram channel ID
            published_at: Publication timestamp
            ab_group: A/B test group (A or B), auto-assigned if None

        Returns:
            True if recorded successfully
        """
        if published_at is None:
            published_at = datetime.now()

        # Auto-assign A/B group (50/50 split)
        if ab_group is None:
            ab_group = random.choice(["A", "B"])

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO post_stats
                    (post_id, message_id, channel_id, ab_group, published_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (post_id, message_id, channel_id, ab_group, published_at.isoformat(), datetime.now().isoformat()),
                )
                conn.commit()
                logger.info(f"Recorded publication: post_id={post_id}, message_id={message_id}, ab_group={ab_group}")
                return True
        except Exception as e:
            logger.error(f"Error recording publication: {e}")
            return False

    def update_post_stats(
        self,
        post_id: int = None,
        message_id: int = None,
        views: int = None,
        forwards: int = None,
        reactions: int = None,
        comments: int = None,
        clicks: int = None,
    ) -> bool:
        """
        Update stats for a post (by post_id or message_id).

        Args:
            post_id: Internal post ID
            message_id: Telegram message ID (alternative)
            views: Number of views
            forwards: Number of forwards/reposts
            reactions: Number of reactions
            comments: Number of comments
            clicks: Number of link clicks

        Returns:
            True if updated successfully
        """
        if not post_id and not message_id:
            logger.error("Either post_id or message_id required")
            return False

        updates = []
        values = []

        if views is not None:
            updates.append("views = ?")
            values.append(views)
        if forwards is not None:
            updates.append("forwards = ?")
            values.append(forwards)
        if reactions is not None:
            updates.append("reactions = ?")
            values.append(reactions)
        if comments is not None:
            updates.append("comments = ?")
            values.append(comments)
        if clicks is not None:
            updates.append("clicks = ?")
            values.append(clicks)

        if not updates:
            return False

        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())

        if post_id:
            where = "post_id = ?"
            values.append(post_id)
        else:
            where = "message_id = ?"
            values.append(message_id)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"UPDATE post_stats SET {', '.join(updates)} WHERE {where}",
                    values,
                )
                conn.commit()
                logger.info(f"Updated stats: post_id={post_id}, message_id={message_id}")
                return True
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
            return False

    def get_post_stats(self, post_id: int = None, message_id: int = None) -> Optional[Dict]:
        """Get stats for a specific post."""
        if not post_id and not message_id:
            return None

        where = "post_id = ?" if post_id else "message_id = ?"
        value = post_id if post_id else message_id

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT * FROM post_stats WHERE {where}",
                (value,),
            )
            row = cursor.fetchone()
            if row:
                stats = dict(row)
                stats["err"] = self._calculate_err(stats)
                return stats
            return None

    def _calculate_err(self, stats: Dict) -> float:
        """
        Calculate Engagement Rate by Reach (ERR).

        ERR = (reactions + comments + forwards) / views * 100
        """
        views = stats.get("views", 0)
        if views == 0:
            return 0.0

        engagement = (
            stats.get("reactions", 0) +
            stats.get("comments", 0) +
            stats.get("forwards", 0)
        )
        return round(engagement / views * 100, 2)

    def get_period_stats(self, days: int = 7) -> Dict:
        """
        Get aggregated stats for a period.

        Args:
            days: Number of days to look back

        Returns:
            Dict with aggregated metrics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_posts,
                    COALESCE(SUM(views), 0) as total_views,
                    COALESCE(SUM(forwards), 0) as total_forwards,
                    COALESCE(SUM(reactions), 0) as total_reactions,
                    COALESCE(SUM(comments), 0) as total_comments,
                    COALESCE(AVG(views), 0) as avg_views,
                    COALESCE(AVG(forwards), 0) as avg_forwards,
                    COALESCE(AVG(reactions), 0) as avg_reactions
                FROM post_stats
                WHERE published_at > datetime('now', '-' || ? || ' days')
                """,
                (days,),
            )
            row = cursor.fetchone()

            total_views = row[1] or 0
            total_engagement = (row[2] or 0) + (row[3] or 0) + (row[4] or 0)
            avg_err = round(total_engagement / total_views * 100, 2) if total_views > 0 else 0

            return {
                "period_days": days,
                "total_posts": row[0] or 0,
                "total_views": total_views,
                "total_forwards": row[2] or 0,
                "total_reactions": row[3] or 0,
                "total_comments": row[4] or 0,
                "avg_views_per_post": round(row[5] or 0, 1),
                "avg_forwards_per_post": round(row[6] or 0, 1),
                "avg_reactions_per_post": round(row[7] or 0, 1),
                "avg_err": avg_err,
            }

    def get_top_posts(self, days: int = 30, limit: int = 5, sort_by: str = "views") -> List[Dict]:
        """
        Get top performing posts.

        Args:
            days: Period to look back
            limit: Number of posts to return
            sort_by: Metric to sort by (views, forwards, reactions, err)

        Returns:
            List of top posts with stats
        """
        valid_sorts = ["views", "forwards", "reactions", "comments"]
        if sort_by not in valid_sorts:
            sort_by = "views"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"""
                SELECT ps.*, pq.post_text, pq.format, pq.article_title
                FROM post_stats ps
                LEFT JOIN post_queue pq ON ps.post_id = pq.id
                WHERE ps.published_at > datetime('now', '-' || ? || ' days')
                ORDER BY ps.{sort_by} DESC
                LIMIT ?
                """,
                (days, limit),
            )
            posts = []
            for row in cursor.fetchall():
                post = dict(row)
                post["err"] = self._calculate_err(post)
                posts.append(post)
            return posts

    def get_daily_breakdown(self, days: int = 7) -> List[Dict]:
        """
        Get daily breakdown of metrics.

        Args:
            days: Number of days

        Returns:
            List of daily stats
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT
                    date(published_at) as day,
                    COUNT(*) as posts,
                    COALESCE(SUM(views), 0) as views,
                    COALESCE(SUM(forwards), 0) as forwards,
                    COALESCE(SUM(reactions), 0) as reactions,
                    COALESCE(AVG(views), 0) as avg_views
                FROM post_stats
                WHERE published_at > datetime('now', '-' || ? || ' days')
                GROUP BY date(published_at)
                ORDER BY day DESC
                """,
                (days,),
            )
            result = []
            for row in cursor.fetchall():
                day_stats = dict(row)
                views = day_stats["views"]
                engagement = day_stats["forwards"] + day_stats["reactions"]
                day_stats["err"] = round(engagement / views * 100, 2) if views > 0 else 0
                result.append(day_stats)
            return result

    def get_ab_comparison(self, days: int = 30) -> Dict:
        """
        Compare A/B test groups performance.

        Args:
            days: Period to analyze

        Returns:
            Dict with comparison metrics for each group
        """
        with sqlite3.connect(self.db_path) as conn:
            results = {}

            for group in ["A", "B"]:
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as posts,
                        COALESCE(SUM(views), 0) as total_views,
                        COALESCE(SUM(forwards), 0) as total_forwards,
                        COALESCE(SUM(reactions), 0) as total_reactions,
                        COALESCE(AVG(views), 0) as avg_views,
                        COALESCE(AVG(forwards), 0) as avg_forwards,
                        COALESCE(AVG(reactions), 0) as avg_reactions
                    FROM post_stats
                    WHERE ab_group = ?
                    AND published_at > datetime('now', '-' || ? || ' days')
                    """,
                    (group, days),
                )
                row = cursor.fetchone()

                total_views = row[1] or 0
                total_engagement = (row[2] or 0) + (row[3] or 0)
                avg_err = round(total_engagement / total_views * 100, 2) if total_views > 0 else 0

                results[group] = {
                    "posts": row[0] or 0,
                    "total_views": total_views,
                    "total_forwards": row[2] or 0,
                    "total_reactions": row[3] or 0,
                    "avg_views": round(row[4] or 0, 1),
                    "avg_forwards": round(row[5] or 0, 2),
                    "avg_reactions": round(row[6] or 0, 2),
                    "avg_err": avg_err,
                }

            # Calculate winner
            if results["A"]["avg_err"] > results["B"]["avg_err"]:
                winner = "A"
                diff = results["A"]["avg_err"] - results["B"]["avg_err"]
            elif results["B"]["avg_err"] > results["A"]["avg_err"]:
                winner = "B"
                diff = results["B"]["avg_err"] - results["A"]["avg_err"]
            else:
                winner = "tie"
                diff = 0

            return {
                "period_days": days,
                "groups": results,
                "winner": winner,
                "err_difference": round(diff, 2),
            }

    def format_ab_comparison_message(self, days: int = 30) -> str:
        """Format A/B comparison as Telegram message."""
        data = self.get_ab_comparison(days)
        groups = data["groups"]

        lines = [
            f"🔬 <b>A/B тест за {days} дней</b>",
            "",
        ]

        for group_name in ["A", "B"]:
            g = groups[group_name]
            lines.extend([
                f"<b>Группа {group_name}:</b>",
                f"  📝 Постов: {g['posts']}",
                f"  👁 Avg views: {g['avg_views']:.0f}",
                f"  📈 Avg ERR: {g['avg_err']}%",
                "",
            ])

        if data["winner"] != "tie":
            lines.append(f"🏆 Лидер: группа <b>{data['winner']}</b> (+{data['err_difference']}% ERR)")
        else:
            lines.append("🤝 Результаты одинаковые")

        return "\n".join(lines)

    def update_daily_metrics(self, date: str = None, subscribers: int = None) -> bool:
        """
        Update or create daily metrics record.

        Args:
            date: Date in YYYY-MM-DD format (default: today)
            subscribers: Current subscriber count

        Returns:
            True if updated successfully
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Calculate metrics from post_stats
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as posts,
                    COALESCE(SUM(views), 0) as views,
                    COALESCE(SUM(forwards), 0) as forwards,
                    COALESCE(SUM(reactions), 0) as reactions
                FROM post_stats
                WHERE date(published_at) = ?
                """,
                (date,),
            )
            row = cursor.fetchone()
            posts = row[0] or 0
            views = row[1] or 0
            forwards = row[2] or 0
            reactions = row[3] or 0

            engagement = forwards + reactions
            avg_err = round(engagement / views * 100, 2) if views > 0 else 0

            conn.execute(
                """
                INSERT OR REPLACE INTO daily_metrics
                (date, posts_published, total_views, total_forwards, total_reactions, avg_err, subscribers, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (date, posts, views, forwards, reactions, avg_err, subscribers, datetime.now().isoformat()),
            )
            conn.commit()
            logger.info(f"Updated daily metrics for {date}")
            return True

    def get_growth_stats(self, days: int = 30) -> Dict:
        """
        Get subscriber growth and trend stats.

        Args:
            days: Period to analyze

        Returns:
            Dict with growth metrics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT date, subscribers
                FROM daily_metrics
                WHERE date > date('now', '-' || ? || ' days')
                AND subscribers > 0
                ORDER BY date ASC
                """,
                (days,),
            )
            rows = cursor.fetchall()

            if len(rows) < 2:
                return {
                    "period_days": days,
                    "start_subscribers": 0,
                    "end_subscribers": 0,
                    "growth": 0,
                    "growth_percent": 0,
                    "avg_daily_growth": 0,
                }

            start_subs = rows[0][1]
            end_subs = rows[-1][1]
            growth = end_subs - start_subs
            growth_percent = round(growth / start_subs * 100, 2) if start_subs > 0 else 0
            avg_daily = round(growth / len(rows), 1)

            return {
                "period_days": days,
                "start_subscribers": start_subs,
                "end_subscribers": end_subs,
                "growth": growth,
                "growth_percent": growth_percent,
                "avg_daily_growth": avg_daily,
            }

    def format_stats_message(self, days: int = 7) -> str:
        """
        Format stats as a Telegram message.

        Args:
            days: Period to report on

        Returns:
            Formatted message string
        """
        stats = self.get_period_stats(days)
        growth = self.get_growth_stats(days)
        top_posts = self.get_top_posts(days=days, limit=3, sort_by="views")

        lines = [
            f"📊 <b>Аналитика за {days} дней</b>",
            "",
            f"📝 Постов: {stats['total_posts']}",
            f"👁 Просмотров: {stats['total_views']:,}",
            f"🔄 Репостов: {stats['total_forwards']}",
            f"❤️ Реакций: {stats['total_reactions']}",
            "",
            f"📈 Средний ERR: {stats['avg_err']}%",
            f"👁 Среднее просмотров/пост: {stats['avg_views_per_post']:.0f}",
        ]

        if growth["end_subscribers"] > 0:
            lines.extend([
                "",
                f"👥 Подписчиков: {growth['end_subscribers']:,}",
                f"📈 Рост: +{growth['growth']} ({growth['growth_percent']}%)",
            ])

        if top_posts:
            lines.extend(["", "🏆 <b>Топ посты:</b>"])
            for i, post in enumerate(top_posts, 1):
                title = post.get("article_title", "")[:30] or "Без названия"
                lines.append(f"{i}. {title}... — {post['views']} 👁")

        return "\n".join(lines)


if __name__ == "__main__":
    # Test analytics
    analytics = Analytics()

    print("Testing analytics module...")

    # Record test publication
    analytics.record_publication(
        post_id=1,
        message_id=12345,
        channel_id="@test_channel",
    )

    # Update stats
    analytics.update_post_stats(
        post_id=1,
        views=500,
        forwards=10,
        reactions=25,
    )

    # Get stats
    stats = analytics.get_post_stats(post_id=1)
    print(f"Post stats: {stats}")

    # Period stats
    period = analytics.get_period_stats(days=7)
    print(f"Period stats: {period}")

    # Format message
    msg = analytics.format_stats_message(days=7)
    print(f"\nFormatted message:\n{msg}")
