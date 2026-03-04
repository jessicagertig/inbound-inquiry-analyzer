"""Configuration loader for categories and sources.

Reads config/categories.yaml to get category names, hex colors, and source options.
The config path is parameterized so tests can pass alternate configs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "categories.yaml"


@dataclass
class CategoryConfig:
    """Parsed configuration for categories and sources."""
    categories: list[dict[str, str]]
    sources: list[str]
    color_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.color_map:
            self.color_map = {cat["name"]: cat["color"] for cat in self.categories}

    @property
    def category_names(self) -> list[str]:
        return [cat["name"] for cat in self.categories]


def load_config(config_path: str | Path | None = None) -> CategoryConfig:
    """Load category and source configuration from a YAML file.

    Args:
        config_path: Path to the categories YAML file. Defaults to
            config/categories.yaml in the repository root.

    Returns:
        CategoryConfig with parsed categories and sources.

    Raises:
        ValueError: If the file is missing, unreadable, or malformed.
    """
    path = Path(config_path) if config_path is not None else _DEFAULT_CONFIG_PATH

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ValueError(f"Config file not found: {path}")
    except OSError as exc:
        raise ValueError(f"Cannot read config file {path}: {exc}") from exc

    try:
        data: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Config file is not valid YAML ({path}): {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(data).__name__}: {path}")

    if "categories" not in data:
        raise ValueError(f"Config file missing required key 'categories': {path}")
    if "sources" not in data:
        raise ValueError(f"Config file missing required key 'sources': {path}")

    categories = data["categories"]
    if not isinstance(categories, list):
        raise ValueError(f"'categories' must be a list in config file: {path}")

    for i, cat in enumerate(categories):
        if not isinstance(cat, dict):
            raise ValueError(f"Category entry {i} must be a mapping in config file: {path}")
        if "name" not in cat:
            raise ValueError(f"Category entry {i} missing 'name' in config file: {path}")
        if "color" not in cat:
            raise ValueError(f"Category entry {i} missing 'color' in config file: {path}")

    sources = data["sources"]
    if not isinstance(sources, list):
        raise ValueError(f"'sources' must be a list in config file: {path}")

    return CategoryConfig(categories=categories, sources=sources)
