"""CoreConfig schema (TDD §20)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApiConfig:
    bind_host: str
    port: int
    auth_token_path: str


@dataclass(frozen=True)
class DataConfig:
    sqlite_path: str
    backup_dir: str


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    retention_days: int
    log_dir: str


@dataclass(frozen=True)
class PipelineConfig:
    repair_max_attempts_default: int
    similarity_tolerance_default: float


@dataclass(frozen=True)
class PluginsConfig:
    products_dir: str


@dataclass(frozen=True)
class CoreConfig:
    api: ApiConfig
    data: DataConfig
    logging: LoggingConfig
    pipeline: PipelineConfig
    plugins: PluginsConfig
