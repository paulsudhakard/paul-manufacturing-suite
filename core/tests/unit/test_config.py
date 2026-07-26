from core.config import ConfigLoader


def test_defaults_only(tmp_path):
    config = ConfigLoader.load(config_path=tmp_path / "nonexistent.yaml", env={})
    assert config.api.bind_host == "127.0.0.1"
    assert config.api.port == 8781
    assert config.pipeline.repair_max_attempts_default == 3


def test_file_overrides_defaults(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api:\n  port: 9999\n")
    config = ConfigLoader.load(config_path=config_file, env={})
    assert config.api.port == 9999
    assert config.api.bind_host == "127.0.0.1"  # untouched fields keep defaults


def test_env_overrides_file_and_defaults(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api:\n  port: 9999\n")
    env = {"PMS_API_PORT": "7777"}
    config = ConfigLoader.load(config_path=config_file, env=env)
    assert config.api.port == 7777  # env beats file


def test_env_type_coercion(tmp_path):
    env = {
        "PMS_API_PORT": "1234",
        "PMS_LOGGING_RETENTION_DAYS": "30",
        "PMS_PIPELINE_SIMILARITY_TOLERANCE_DEFAULT": "0.8",
    }
    config = ConfigLoader.load(config_path=tmp_path / "none.yaml", env=env)
    assert config.api.port == 1234 and isinstance(config.api.port, int)
    assert config.logging.retention_days == 30 and isinstance(config.logging.retention_days, int)
    assert config.pipeline.similarity_tolerance_default == 0.8
    assert isinstance(config.pipeline.similarity_tolerance_default, float)


def test_full_precedence_chain_combined(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "api:\n  port: 1111\n  bind_host: 127.0.0.1\n"
        "logging:\n  level: DEBUG\n"
    )
    env = {"PMS_API_PORT": "2222"}  # only overrides port, not level
    config = ConfigLoader.load(config_path=config_file, env=env)
    assert config.api.port == 2222  # env wins
    assert config.logging.level == "DEBUG"  # file wins (no env override)
    assert config.plugins.products_dir == "./products"  # default wins (untouched)
