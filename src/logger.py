"""Logging configuration with file rotation."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    name: str = "news_bot",
    log_dir: Path = Path("logs"),
    log_level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 5,
    console_output: bool = True,
) -> logging.Logger:
    """
    Configure logging with file rotation and console output.

    Args:
        name: Logger name (used for log file names)
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        max_bytes: Max size per log file before rotation (default 5MB)
        backup_count: Number of backup files to keep
        console_output: Whether to also log to console

    Returns:
        Configured logger instance
    """
    # Create logs directory
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get or create logger
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Set level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Main log file with rotation (by size)
    log_file = log_dir / f"{name}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # Capture all levels in file
    logger.addHandler(file_handler)

    # Error-only log file
    error_file = log_dir / f"{name}_errors.log"
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str = "news_bot") -> logging.Logger:
    """
    Get existing logger or create new one with default settings.

    Args:
        name: Logger name (can use dot notation for hierarchy)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # If no handlers, this is a child logger - just return it
        # It will inherit from parent or use default config
        pass
    return logger
