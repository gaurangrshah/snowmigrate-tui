"""Connection models for source databases and Snowflake targets."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr


class SourceType(str, Enum):
    """Supported source database types."""

    POSTGRES = "postgres"
    MYSQL = "mysql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    JDBC = "jdbc"


class ConnectionStatus(str, Enum):
    """Connection test status."""

    UNKNOWN = "unknown"
    CONNECTED = "connected"
    FAILED = "failed"
    TESTING = "testing"


class SourceConnection(BaseModel):
    """Source database connection configuration."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    type: SourceType
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: SecretStr
    jdbc_options: dict[str, str] = Field(default_factory=dict)
    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    last_tested: datetime | None = None
    error_message: str | None = None

    @property
    def display_host(self) -> str:
        """Return host:port for display."""
        return f"{self.host}:{self.port}"

    @property
    def jdbc_url(self) -> str:
        """Generate JDBC URL based on source type."""
        base_urls = {
            SourceType.POSTGRES: f"jdbc:postgresql://{self.host}:{self.port}/{self.database}",
            SourceType.MYSQL: f"jdbc:mysql://{self.host}:{self.port}/{self.database}",
            SourceType.ORACLE: f"jdbc:oracle:thin:@{self.host}:{self.port}:{self.database}",
            SourceType.SQLSERVER: (
                f"jdbc:sqlserver://{self.host}:{self.port};databaseName={self.database}"
            ),
            SourceType.JDBC: self.jdbc_options.get("url", ""),
        }
        return base_urls.get(self.type, "")


class SnowflakeConnection(BaseModel):
    """Snowflake target connection configuration."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    account: str = Field(..., min_length=1, description="Snowflake account identifier")
    warehouse: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1)
    schema_name: str = Field(default="PUBLIC")
    username: str = Field(..., min_length=1)
    password: SecretStr
    role: str | None = None
    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    last_tested: datetime | None = None
    error_message: str | None = None

    @property
    def display_account(self) -> str:
        """Return account info for display."""
        return f"{self.account} / {self.warehouse}"


class ConnectionTestResult(BaseModel):
    """Result of a connection test."""

    success: bool
    message: str
    latency_ms: float | None = None
    server_version: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
