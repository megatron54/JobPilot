"""Persistence for user search criteria and autopilot config (JSON files)."""

from __future__ import annotations

import json
import logging

from .config import settings
from .models import AutopilotConfig, SearchCriteria

logger = logging.getLogger("jobpilot.autopilot.store")


def load_search_criteria() -> SearchCriteria:
    path = settings.search_criteria_path
    if not path.exists():
        return SearchCriteria()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SearchCriteria(**data)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Failed to load search criteria: %s", exc)
        return SearchCriteria()


def save_search_criteria(criteria: SearchCriteria) -> None:
    path = settings.search_criteria_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(criteria.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Saved search criteria to %s", path)


def load_config() -> AutopilotConfig:
    path = settings.config_path
    if not path.exists():
        return AutopilotConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AutopilotConfig(**data)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Failed to load autopilot config: %s", exc)
        return AutopilotConfig()


def save_config(config: AutopilotConfig) -> None:
    path = settings.config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Saved autopilot config to %s", path)
