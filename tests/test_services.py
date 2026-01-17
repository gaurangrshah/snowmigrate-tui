"""Tests for services."""

import pytest
from pydantic import SecretStr

from snowmigrate.models.connection import (
    ConnectionStatus,
    SnowflakeConnection,
    SourceConnection,
    SourceType,
)
from snowmigrate.models.migration import MigrationConfig, MigrationStatus, TableSelection
from snowmigrate.services.connection_manager import ConnectionManager
from snowmigrate.services.migration_engine import MigrationEngine


class TestConnectionManager:
    """Tests for ConnectionManager service."""

    def test_add_source_connection(self):
        """Test adding a source connection."""
        manager = ConnectionManager()
        conn = SourceConnection(
            name="Test",
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="db",
            username="user",
            password=SecretStr("pass"),
        )

        conn_id = manager.add_source_connection(conn)

        assert conn_id == conn.id
        assert len(manager.list_source_connections()) == 1

    def test_add_snowflake_connection(self):
        """Test adding a Snowflake connection."""
        manager = ConnectionManager()
        conn = SnowflakeConnection(
            name="Snowflake",
            account="account",
            warehouse="WH",
            database="DB",
            username="user",
            password=SecretStr("pass"),
        )

        conn_id = manager.add_snowflake_connection(conn)

        assert conn_id == conn.id
        assert len(manager.list_snowflake_connections()) == 1

    def test_get_source_connection(self):
        """Test retrieving a source connection."""
        manager = ConnectionManager()
        conn = SourceConnection(
            name="Test",
            type=SourceType.MYSQL,
            host="mysql.local",
            port=3306,
            database="mydb",
            username="root",
            password=SecretStr("secret"),
        )

        conn_id = manager.add_source_connection(conn)
        retrieved = manager.get_source_connection(conn_id)

        assert retrieved is not None
        assert retrieved.name == "Test"
        assert retrieved.type == SourceType.MYSQL

    def test_get_nonexistent_connection(self):
        """Test retrieving a non-existent connection."""
        manager = ConnectionManager()

        result = manager.get_source_connection("nonexistent")

        assert result is None

    def test_delete_source_connection(self):
        """Test deleting a source connection."""
        manager = ConnectionManager()
        conn = SourceConnection(
            name="ToDelete",
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="db",
            username="u",
            password=SecretStr("p"),
        )

        conn_id = manager.add_source_connection(conn)
        assert len(manager.list_source_connections()) == 1

        manager.delete_source_connection(conn_id)
        assert len(manager.list_source_connections()) == 0

    def test_update_source_connection(self):
        """Test updating a source connection."""
        manager = ConnectionManager()
        conn = SourceConnection(
            name="Original",
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="db",
            username="u",
            password=SecretStr("p"),
        )

        conn_id = manager.add_source_connection(conn)

        updated = SourceConnection(
            name="Updated",
            type=SourceType.POSTGRES,
            host="newhost",
            port=5433,
            database="newdb",
            username="newuser",
            password=SecretStr("newpass"),
        )

        manager.update_source_connection(conn_id, updated)
        retrieved = manager.get_source_connection(conn_id)

        assert retrieved is not None
        assert retrieved.name == "Updated"
        assert retrieved.host == "newhost"

    def test_update_nonexistent_connection_raises(self):
        """Test that updating non-existent connection raises."""
        manager = ConnectionManager()
        conn = SourceConnection(
            name="Test",
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="db",
            username="u",
            password=SecretStr("p"),
        )

        with pytest.raises(KeyError):
            manager.update_source_connection("nonexistent", conn)


class TestMigrationEngine:
    """Tests for MigrationEngine service."""

    def test_create_migration(self):
        """Test creating a migration."""
        manager = ConnectionManager()
        engine = MigrationEngine(manager)

        config = MigrationConfig(
            source_connection_id="source-1",
            target_connection_id="target-1",
            staging_area_id="s3-prod",
            tables=[
                TableSelection(schema_name="public", table_name="users"),
                TableSelection(schema_name="public", table_name="orders"),
            ],
        )

        migration = engine.create_migration(config)

        assert migration.status == MigrationStatus.QUEUED
        assert len(migration.tables) == 2
        assert migration.progress.total_tables == 2

    def test_list_migrations(self):
        """Test listing migrations."""
        manager = ConnectionManager()
        engine = MigrationEngine(manager)

        config = MigrationConfig(
            source_connection_id="s1",
            target_connection_id="t1",
            staging_area_id="st1",
            tables=[TableSelection(schema_name="s", table_name="t")],
        )

        engine.create_migration(config)
        engine.create_migration(config)

        migrations = engine.list_migrations()
        assert len(migrations) == 2

    def test_get_migration(self):
        """Test getting a specific migration."""
        manager = ConnectionManager()
        engine = MigrationEngine(manager)

        config = MigrationConfig(
            source_connection_id="s1",
            target_connection_id="t1",
            staging_area_id="st1",
            tables=[TableSelection(schema_name="s", table_name="t")],
        )

        created = engine.create_migration(config)
        retrieved = engine.get_migration(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_migration(self):
        """Test getting a non-existent migration."""
        manager = ConnectionManager()
        engine = MigrationEngine(manager)

        result = engine.get_migration("nonexistent")
        assert result is None

    def test_list_active_migrations(self):
        """Test listing only active migrations."""
        manager = ConnectionManager()
        engine = MigrationEngine(manager)

        config = MigrationConfig(
            source_connection_id="s1",
            target_connection_id="t1",
            staging_area_id="st1",
            tables=[TableSelection(schema_name="s", table_name="t")],
        )

        m1 = engine.create_migration(config)
        m2 = engine.create_migration(config)

        m2.status = MigrationStatus.COMPLETED

        active = engine.list_active_migrations()
        assert len(active) == 1
        assert active[0].id == m1.id
