"""Tests for data models."""

import pytest
from pydantic import SecretStr

from snowmigrate.models.connection import (
    ConnectionStatus,
    ConnectionTestResult,
    SnowflakeConnection,
    SourceConnection,
    SourceType,
)
from snowmigrate.models.migration import (
    Migration,
    MigrationConfig,
    MigrationProgress,
    MigrationStatus,
    TableSelection,
)
from snowmigrate.models.staging import StagingArea, StagingType


class TestSourceConnection:
    """Tests for SourceConnection model."""

    def test_create_postgres_connection(self):
        """Test creating a PostgreSQL connection."""
        conn = SourceConnection(
            name="Test DB",
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password=SecretStr("pass"),
        )

        assert conn.name == "Test DB"
        assert conn.type == SourceType.POSTGRES
        assert conn.display_host == "localhost:5432"
        assert "postgresql" in conn.jdbc_url

    def test_create_mysql_connection(self):
        """Test creating a MySQL connection."""
        conn = SourceConnection(
            name="MySQL DB",
            type=SourceType.MYSQL,
            host="mysql.example.com",
            port=3306,
            database="mydb",
            username="root",
            password=SecretStr("secret"),
        )

        assert conn.type == SourceType.MYSQL
        assert "mysql" in conn.jdbc_url

    def test_connection_status_default(self):
        """Test default connection status."""
        conn = SourceConnection(
            name="Test",
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="db",
            username="u",
            password=SecretStr("p"),
        )

        assert conn.status == ConnectionStatus.UNKNOWN
        assert conn.last_tested is None


class TestSnowflakeConnection:
    """Tests for SnowflakeConnection model."""

    def test_create_snowflake_connection(self):
        """Test creating a Snowflake connection."""
        conn = SnowflakeConnection(
            name="Prod Snowflake",
            account="myaccount.us-east-1",
            warehouse="COMPUTE_WH",
            database="PROD_DB",
            schema_name="PUBLIC",
            username="snowuser",
            password=SecretStr("snowpass"),
        )

        assert conn.account == "myaccount.us-east-1"
        assert conn.display_account == "myaccount.us-east-1 / COMPUTE_WH"

    def test_snowflake_with_role(self):
        """Test Snowflake connection with role."""
        conn = SnowflakeConnection(
            name="Admin",
            account="account",
            warehouse="WH",
            database="DB",
            username="admin",
            password=SecretStr("pass"),
            role="ACCOUNTADMIN",
        )

        assert conn.role == "ACCOUNTADMIN"


class TestConnectionTestResult:
    """Tests for ConnectionTestResult model."""

    def test_successful_result(self):
        """Test successful connection result."""
        result = ConnectionTestResult(
            success=True,
            message="Connected",
            latency_ms=45.5,
            server_version="14.5",
        )

        assert result.success
        assert result.latency_ms == 45.5

    def test_failed_result(self):
        """Test failed connection result."""
        result = ConnectionTestResult(
            success=False,
            message="Connection refused",
        )

        assert not result.success
        assert result.latency_ms is None


class TestTableSelection:
    """Tests for TableSelection model."""

    def test_full_name(self):
        """Test fully qualified table name."""
        table = TableSelection(
            schema_name="sales",
            table_name="orders",
            row_count=1000000,
        )

        assert table.full_name == "sales.orders"


class TestMigrationProgress:
    """Tests for MigrationProgress model."""

    def test_percentage_calculation(self):
        """Test progress percentage calculation."""
        progress = MigrationProgress(
            total_tables=4,
            completed_tables=2,
            total_rows=1000,
            migrated_rows=500,
        )

        assert progress.percentage == 50.0

    def test_percentage_zero_total(self):
        """Test percentage with zero total rows."""
        progress = MigrationProgress(
            total_tables=4,
            completed_tables=2,
            total_rows=0,
            migrated_rows=0,
        )

        assert progress.percentage == 50.0  # Falls back to table-based

    def test_eta_display_seconds(self):
        """Test ETA display for seconds."""
        progress = MigrationProgress(eta_seconds=45)
        assert progress.eta_display == "45s"

    def test_eta_display_minutes(self):
        """Test ETA display for minutes."""
        progress = MigrationProgress(eta_seconds=185)
        assert progress.eta_display == "3m 5s"

    def test_eta_display_hours(self):
        """Test ETA display for hours."""
        progress = MigrationProgress(eta_seconds=7320)
        assert progress.eta_display == "2h 2m"


class TestMigration:
    """Tests for Migration model."""

    def test_create_migration(self):
        """Test creating a migration."""
        tables = [
            TableSelection(schema_name="public", table_name="users"),
            TableSelection(schema_name="public", table_name="orders"),
        ]

        migration = Migration(
            source_connection_id="source-123",
            target_connection_id="target-456",
            staging_area_id="s3-prod",
            tables=tables,
        )

        assert migration.status == MigrationStatus.QUEUED
        assert migration.source_display == "2 tables"

    def test_single_table_display(self):
        """Test source display with single table."""
        migration = Migration(
            source_connection_id="s",
            target_connection_id="t",
            staging_area_id="st",
            tables=[TableSelection(schema_name="sales", table_name="orders")],
        )

        assert migration.source_display == "sales.orders"


class TestStagingArea:
    """Tests for StagingArea model."""

    def test_s3_staging(self):
        """Test S3 staging area."""
        staging = StagingArea(
            id="s3-prod",
            name="Production S3",
            type=StagingType.S3,
            path="s3://bucket/path",
        )

        assert staging.type_icon == "S3"
        assert staging.type_display == "AWS S3"

    def test_internal_staging(self):
        """Test internal staging area."""
        staging = StagingArea(
            id="internal",
            name="Internal Stage",
            type=StagingType.INTERNAL,
            path="@MIGRATION_STAGE",
        )

        assert staging.type_icon == "@"
        assert staging.type_display == "Snowflake Internal Stage"
