"""Application configuration."""

import os
from pathlib import Path

from pydantic import BaseModel, Field


class CLIConfig(BaseModel):
    """CLI tool configuration."""

    path: str = Field(
        default_factory=lambda: os.environ.get("SNOWMIGRATE_CLI_PATH", "/usr/local/bin/migrate-tool")
    )
    timeout_seconds: int = 3600


class PerformanceConfig(BaseModel):
    """Performance settings."""

    max_concurrent_migrations: int = Field(
        default_factory=lambda: int(os.environ.get("SNOWMIGRATE_MAX_CONCURRENT", "10"))
    )
    progress_poll_interval_ms: int = 1000
    metadata_timeout_seconds: int = 30
    connection_test_timeout_seconds: int = 10


class UIConfig(BaseModel):
    """UI settings."""

    theme: str = "dark"
    show_row_counts: bool = True
    sample_data_rows: int = 10


class AppConfig(BaseModel):
    """Main application configuration."""

    cli: CLIConfig = Field(default_factory=CLIConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    log_level: str = Field(
        default_factory=lambda: os.environ.get("SNOWMIGRATE_LOG_LEVEL", "INFO")
    )

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        """Load configuration from file or defaults."""
        if config_path is None:
            config_path = Path.home() / ".snowmigrate" / "config.toml"

        if config_path.exists():
            try:
                import tomllib

                with open(config_path, "rb") as f:
                    data = tomllib.load(f)
                return cls.model_validate(data)
            except Exception:
                pass

        return cls()


# Global config instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config
