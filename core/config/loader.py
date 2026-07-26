"""ConfigLoader — precedence order per TDD §20:
per-job override → environment variables → config.yaml file → defaults.

Sprint 1 implements the bottom three tiers only; per-job override doesn't
exist until Jobs do (Sprint 11) — Sprint 1's task list says this
explicitly.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.config.defaults import DEFAULTS
from core.config.schema import (
    ApiConfig,
    CoreConfig,
    DataConfig,
    LoggingConfig,
    PipelineConfig,
    PluginsConfig,
)

# Maps PMS_<SECTION>_<FIELD> env vars onto (section, field, caster).
_ENV_FIELD_MAP: dict[str, tuple[str, str, type]] = {
    "PMS_API_BIND_HOST": ("api", "bind_host", str),
    "PMS_API_PORT": ("api", "port", int),
    "PMS_API_AUTH_TOKEN_PATH": ("api", "auth_token_path", str),
    "PMS_DATA_SQLITE_PATH": ("data", "sqlite_path", str),
    "PMS_DATA_BACKUP_DIR": ("data", "backup_dir", str),
    "PMS_LOGGING_LEVEL": ("logging", "level", str),
    "PMS_LOGGING_RETENTION_DAYS": ("logging", "retention_days", int),
    "PMS_LOGGING_LOG_DIR": ("logging", "log_dir", str),
    "PMS_PIPELINE_REPAIR_MAX_ATTEMPTS_DEFAULT": (
        "pipeline",
        "repair_max_attempts_default",
        int,
    ),
    "PMS_PIPELINE_SIMILARITY_TOLERANCE_DEFAULT": (
        "pipeline",
        "similarity_tolerance_default",
        float,
    ),
    "PMS_PLUGINS_PRODUCTS_DIR": ("plugins", "products_dir", str),
}


class ConfigLoader:
    @staticmethod
    def load(
        config_path: Path | str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CoreConfig:
        """Resolve a CoreConfig from defaults → file → env, in that order.

        `env` defaults to the real process environment; tests inject a
        fake mapping instead so config precedence tests never depend on
        (or mutate) the real environment.
        """
        merged: dict[str, Any] = copy.deepcopy(DEFAULTS)

        if config_path is not None:
            path = Path(config_path)
            if path.is_file():
                file_values = yaml.safe_load(path.read_text()) or {}
                ConfigLoader._deep_merge(merged, file_values)

        env_map = os.environ if env is None else env
        ConfigLoader._apply_env(merged, env_map)

        return CoreConfig(
            api=ApiConfig(**merged["api"]),
            data=DataConfig(**merged["data"]),
            logging=LoggingConfig(**merged["logging"]),
            pipeline=PipelineConfig(**merged["pipeline"]),
            plugins=PluginsConfig(**merged["plugins"]),
        )

    @staticmethod
    def _deep_merge(base: dict, overrides: Mapping) -> None:
        for key, value in overrides.items():
            if isinstance(value, Mapping) and isinstance(base.get(key), dict):
                ConfigLoader._deep_merge(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _apply_env(merged: dict, env_map: Mapping[str, str]) -> None:
        for env_var, (section, field, caster) in _ENV_FIELD_MAP.items():
            if env_var in env_map:
                merged[section][field] = caster(env_map[env_var])
