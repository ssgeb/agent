from app.config.settings import Settings
import yaml


def test_settings_default_to_sqlite_when_no_database_url():
    settings = Settings(database_url="", db_driver="sqlite", sqlite_path="./unit.db")
    assert settings.resolved_database_url == "sqlite:///./unit.db"


def test_settings_build_mysql_url_from_parts():
    settings = Settings(
        database_url="",
        db_driver="mysql",
        mysql_host="127.0.0.1",
        mysql_port=3306,
        mysql_user="root",
        mysql_password="pass@123",
        mysql_database="travel_planner",
    )
    assert settings.resolved_database_url == (
        "mysql+pymysql://root:pass%40123@127.0.0.1:3306/travel_planner"
    )


def test_settings_database_url_has_highest_priority():
    settings = Settings(
        database_url="sqlite:///./override.db",
        db_driver="mysql",
        mysql_host="localhost",
        mysql_user="root",
    )
    assert settings.resolved_database_url == "sqlite:///./override.db"


def test_settings_loads_single_yaml_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
app:
  name: yaml-travel
  debug: false
llm:
  model: qwen-max
  api_key: yaml-key
features:
  use_mock_only: false
  enable_amap_mcp: true
  enable_agent_reach: true
  enable_real_providers: true
database:
  driver: mysql
  mysql:
    host: db.local
    port: 3307
    user: traveler
    password: secret
    database: travel_prod
redis:
  url: redis://127.0.0.1:6379/1
providers:
  transport:
    primary: ctrip
    ctrip:
      enabled: true
      cookie: fill_me_later
agent_reach:
  enabled: true
  channels:
    xiaohongshu:
      enabled: true
      cookie: fill_me_later
amap_mcp:
  provider: aliyun
  aliyun:
    mode: sse
    sse_url: https://example.com/amap/sse
    api_key: amap-key
  amap:
    mode: streamable-http
    sse_url: https://mcp.amap.com/mcp
    api_key: direct-key
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_FILE", str(config_file))
    monkeypatch.delenv("LLM_MODEL", raising=False)

    settings = Settings()

    assert settings.app_name == "yaml-travel"
    assert settings.debug is False
    assert settings.llm_model == "qwen-max"
    assert settings.llm_api_key == "yaml-key"
    assert settings.use_mock_only is False
    assert settings.enable_amap_mcp is True
    assert settings.enable_agent_reach is True
    assert settings.enable_real_providers is True
    assert settings.redis_url == "redis://127.0.0.1:6379/1"
    assert settings.resolved_database_url == (
        "mysql+pymysql://traveler:secret@db.local:3307/travel_prod"
    )
    assert settings.providers["transport"]["ctrip"]["cookie"] == "fill_me_later"
    assert settings.agent_reach["channels"]["xiaohongshu"]["cookie"] == "fill_me_later"
    assert settings.amap_mcp["provider"] == "aliyun"
    assert settings.amap_mcp["aliyun"]["mode"] == "sse"
    assert settings.amap_mcp["aliyun"]["sse_url"] == "https://example.com/amap/sse"
    assert settings.amap_mcp["amap"]["sse_url"] == "https://mcp.amap.com/mcp"


def test_settings_env_overrides_yaml_config(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
llm:
  model: qwen-max
features:
  use_mock_only: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.setenv("USE_MOCK_ONLY", "true")

    settings = Settings()

    assert settings.llm_model == "env-model"
    assert settings.use_mock_only is True


def test_config_example_yaml_is_parseable_and_contains_cookie_slots():
    with open("config.example.yaml", "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    assert config["features"]["use_mock_only"] is False
    assert config["features"]["enable_amap_mcp"] is False
    assert config["features"]["enable_agent_reach"] is True
    assert config["amap_mcp"]["provider"] == "aliyun"
    assert config["amap_mcp"]["aliyun"]["sse_url"] == "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp"
    assert config["amap_mcp"]["amap"]["sse_url"] == "https://mcp.amap.com/mcp"
    assert config["providers"]["transport"]["ctrip"]["cookie"] == ""
    assert config["providers"]["hotel"]["meituan"]["cookie"] == ""
    assert config["agent_reach"]["channels"]["xiaohongshu"]["cookie"] == ""
