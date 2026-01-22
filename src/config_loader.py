"""Загрузчик YAML конфигов."""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml

_cache: Dict[str, Any] = {}
CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_yaml(filename: str) -> Dict[str, Any]:
    """Загрузить YAML файл из config/."""
    if filename in _cache:
        return _cache[filename]

    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    _cache[filename] = data
    return data


def get_prompts() -> Dict[str, Any]:
    """Получить промпты из prompts.yaml."""
    return load_yaml("prompts.yaml")


def get_thresholds() -> Dict[str, Any]:
    """Получить пороги из thresholds.yaml."""
    return load_yaml("thresholds.yaml")


def get_sources() -> Dict[str, Any]:
    """Получить RSS источники из sources.yaml."""
    return load_yaml("sources.yaml")


def get_schedule() -> Dict[str, Any]:
    """Получить расписание из schedule.yaml."""
    return load_yaml("schedule.yaml")


def get_image_template(category: str) -> Optional[str]:
    """Получить шаблон промпта для картинки по категории."""
    prompts = get_prompts()
    templates = prompts.get("image_templates", {})
    return templates.get(category)


def clear_cache() -> None:
    """Очистить кэш (для тестов)."""
    _cache.clear()
