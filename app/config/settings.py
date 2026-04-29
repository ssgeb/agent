from pathlib import Path
import os
from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus
import yaml


def _deep_get(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


YAML_FIELD_PATHS: dict[str, tuple[str, ...]] = {
    "app_name": ("app", "name"),
    "app_version": ("app", "version"),
    "debug": ("app", "debug"),
    "llm_provider": ("llm", "provider"),
    "llm_model": ("llm", "model"),
    "llm_api_key": ("llm", "api_key"),
    "llm_base_url": ("llm", "base_url"),
    "max_tokens": ("llm", "max_tokens"),
    "temperature": ("llm", "temperature"),
    "use_mock_only": ("features", "use_mock_only"),
    "enable_amap_mcp": ("features", "enable_amap_mcp"),
    "enable_agent_reach": ("features", "enable_agent_reach"),
    "enable_real_providers": ("features", "enable_real_providers"),
    "tool_timeout": ("tools", "timeout_seconds"),
    "session_timeout": ("session", "timeout"),
    "max_history_length": ("session", "max_history_length"),
    "db_driver": ("database", "driver"),
    "sqlite_path": ("database", "sqlite_path"),
    "database_url": ("database", "database_url"),
    "mysql_host": ("database", "mysql", "host"),
    "mysql_port": ("database", "mysql", "port"),
    "mysql_user": ("database", "mysql", "user"),
    "mysql_password": ("database", "mysql", "password"),
    "mysql_database": ("database", "mysql", "database"),
    "redis_url": ("redis", "url"),
    "max_task_retries": ("tasks", "max_retries"),
    "session_lock_ttl_seconds": ("tasks", "session_lock_ttl_seconds"),
    "idempotency_key_ttl_seconds": ("tasks", "idempotency_key_ttl_seconds"),
    "task_recovery_stale_seconds": ("tasks", "recovery_stale_seconds"),
    "providers": ("providers",),
    "amap_mcp": ("amap_mcp",),
    "agent_reach": ("agent_reach",),
}


def _load_yaml_settings() -> dict[str, Any]:
    config_path = Path(os.environ.get("APP_CONFIG_FILE", "config.yaml"))
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        return {}

    values: dict[str, Any] = {}
    for field_name, yaml_path in YAML_FIELD_PATHS.items():
        if field_name.upper() in os.environ:
            continue
        value = _deep_get(loaded, yaml_path)
        if value is not None:
            values[field_name] = value
    return values


class Settings(BaseSettings):
    def __init__(self, **values):
        yaml_values = _load_yaml_settings()
        yaml_values.update(values)
        super().__init__(**yaml_values)

    app_name: str = "travel-planner"
    app_version: str = "1.0.0"
    debug: bool = True
    llm_provider: str = "aliyun"
    llm_model: str = "qwen-plus"
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    max_tokens: int = 1000
    temperature: float = 0.7
    use_mock_only: bool = False
    enable_amap_mcp: bool = False
    enable_agent_reach: bool = True
    enable_real_providers: bool = True
    tool_timeout: int = 30
    session_timeout: int = 3600
    max_history_length: int = 50
    db_driver: str = "sqlite"
    sqlite_path: str = "./travel_planner.db"
    database_url: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "travel_planner"
    redis_url: str = ""
    max_task_retries: int = 3
    session_lock_ttl_seconds: int = 60
    idempotency_key_ttl_seconds: int = 24 * 60 * 60
    task_recovery_stale_seconds: int = 5 * 60
    providers: dict[str, Any] = Field(default_factory=dict)
    amap_mcp: dict[str, Any] = Field(default_factory=dict)
    agent_reach: dict[str, Any] = Field(default_factory=dict)

    model_config = SettingsConfigDict(extra="ignore")

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production", "0", "false", "off", "no"}:
                return False
            if lowered in {"debug", "1", "true", "on", "yes"}:
                return True
        return value

    @property
    def resolved_database_url(self) -> str:
        """优先使用 DATABASE_URL；为空时根据 MySQL 参数自动拼接。"""
        if self.database_url.strip():
            return self.database_url.strip()

        if self.db_driver.strip().lower() != "mysql":
            return f"sqlite:///{self.sqlite_path}"

        if self.mysql_password:
            encoded_password = quote_plus(self.mysql_password)
        else:
            encoded_password = ""

        auth_part = self.mysql_user
        if encoded_password:
            auth_part = f"{self.mysql_user}:{encoded_password}"

        return (
            f"mysql+pymysql://{auth_part}@"
            f"{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )
