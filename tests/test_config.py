"""Tests for configuration."""

import os
import pytest

from snowmigrate.config import AppConfig, CLIConfig, PerformanceConfig, UIConfig, get_config


class TestCLIConfig:
    """Tests for CLI configuration."""

    def test_default_values(self):
        """Test default CLI config values."""
        config = CLIConfig()

        assert config.timeout_seconds == 3600

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("SNOWMIGRATE_CLI_PATH", "/custom/path")

        config = CLIConfig()

        assert config.path == "/custom/path"


class TestPerformanceConfig:
    """Tests for performance configuration."""

    def test_default_values(self):
        """Test default performance config values."""
        config = PerformanceConfig()

        assert config.max_concurrent_migrations == 10
        assert config.progress_poll_interval_ms == 1000
        assert config.metadata_timeout_seconds == 30
        assert config.connection_test_timeout_seconds == 10

    def test_env_override(self, monkeypatch):
        """Test environment variable override for max concurrent."""
        monkeypatch.setenv("SNOWMIGRATE_MAX_CONCURRENT", "5")

        config = PerformanceConfig()

        assert config.max_concurrent_migrations == 5


class TestUIConfig:
    """Tests for UI configuration."""

    def test_default_values(self):
        """Test default UI config values."""
        config = UIConfig()

        assert config.theme == "dark"
        assert config.show_row_counts is True
        assert config.sample_data_rows == 10


class TestAppConfig:
    """Tests for main application configuration."""

    def test_default_values(self):
        """Test default app config values."""
        config = AppConfig()

        assert config.log_level == "INFO"
        assert isinstance(config.cli, CLIConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.ui, UIConfig)

    def test_env_log_level_override(self, monkeypatch):
        """Test environment variable override for log level."""
        monkeypatch.setenv("SNOWMIGRATE_LOG_LEVEL", "DEBUG")

        config = AppConfig()

        assert config.log_level == "DEBUG"

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from non-existent file returns defaults."""
        config = AppConfig.load(tmp_path / "nonexistent.toml")

        assert config.log_level == "INFO"


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_config(self):
        """Test that get_config returns a config."""
        import snowmigrate.config as config_module

        config_module._config = None

        config = get_config()

        assert isinstance(config, AppConfig)

    def test_singleton(self):
        """Test that get_config returns the same instance."""
        import snowmigrate.config as config_module

        config_module._config = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2
