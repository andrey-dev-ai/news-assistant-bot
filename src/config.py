"""Configuration management with Pydantic validation."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API
    anthropic_api_key: str = Field(
        ...,
        alias="ANTHROPIC_API_KEY",
        min_length=50,
        description="Claude API key from console.anthropic.com"
    )

    # OpenAI API (для GPT Image 1 Mini)
    openai_api_key: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_KEY",
        description="OpenAI API key for image generation"
    )

    # Telegram Bot
    telegram_bot_token: str = Field(
        ...,
        alias="TELEGRAM_BOT_TOKEN",
        min_length=40,
        description="Telegram bot token from @BotFather"
    )

    telegram_user_id: str = Field(
        ...,
        alias="TELEGRAM_USER_ID",
        description="Your Telegram user ID"
    )

    telegram_channel_id: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_CHANNEL_ID",
        description="Telegram channel ID for publishing digests"
    )

    # Scheduler
    digest_times: str = Field(
        default="08:00",
        alias="DIGEST_TIMES",
        description="Digest times in HH:MM format, comma-separated"
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )

    log_dir: Path = Field(
        default=Path("logs"),
        alias="LOG_DIR",
        description="Directory for log files"
    )

    # AI Model settings
    ai_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use"
    )

    ai_max_tokens: int = Field(
        default=4000,
        ge=100,
        le=8000,
        description="Max tokens for AI response"
    )

    # RSS settings
    rss_config_path: Path = Field(
        default=Path("config/rss_feeds.json"),
        description="Path to RSS feeds config"
    )

    rss_hours_back: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours to look back for news"
    )

    # Database
    db_path: Path = Field(
        default=Path("data/news_bot.db"),
        description="Path to SQLite database"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    @field_validator("telegram_user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate that user ID contains only digits."""
        if not v.isdigit():
            raise ValueError("TELEGRAM_USER_ID must contain only digits")
        return v

    @field_validator("telegram_channel_id")
    @classmethod
    def validate_channel_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate channel ID format."""
        if v is None or v == "":
            return None
        # Channel ID can be @username or numeric ID (negative for channels)
        if not (v.startswith("@") or v.lstrip("-").isdigit()):
            raise ValueError(
                "TELEGRAM_CHANNEL_ID must be @username or numeric ID"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {valid_levels}")
        return v_upper

    def get_digest_times_list(self) -> List[str]:
        """Parse digest times string into list."""
        return [t.strip() for t in self.digest_times.split(",") if t.strip()]


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def validate_config() -> bool:
    """
    Validate configuration on startup.

    Returns:
        True if configuration is valid.

    Raises:
        ValueError: If configuration is invalid.
    """
    try:
        settings = get_settings()
        # Ensure log directory can be created
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
