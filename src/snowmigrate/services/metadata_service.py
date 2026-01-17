"""Database metadata introspection service."""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from snowmigrate.config import get_config
from snowmigrate.models.connection import SourceConnection, SourceType
from snowmigrate.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


def _validate_identifier(name: str) -> str:
    """Validate and sanitize SQL identifier to prevent injection.

    Only allows alphanumeric characters, underscores, and dots.
    Raises ValueError if invalid characters are found.
    """
    if not name:
        raise ValueError("Identifier cannot be empty")

    # Allow only alphanumeric, underscore, and dot (for schema.table)
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid identifier: {name}")

    return name


def _escape_identifier(name: str) -> str:
    """Escape SQL identifier by doubling any quotes and wrapping in quotes.

    This is used for identifiers that may contain special characters.
    """
    # Validate first
    _validate_identifier(name)
    # Double any existing quotes and wrap in double quotes
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


@dataclass
class DatabaseInfo:
    """Database metadata."""

    name: str
    schema_count: int | None = None


@dataclass
class SchemaInfo:
    """Schema metadata."""

    name: str
    table_count: int | None = None


@dataclass
class TableInfo:
    """Table metadata."""

    schema_name: str
    name: str
    row_count: int | None = None
    size_bytes: int | None = None
    table_type: str = "TABLE"

    @property
    def full_name(self) -> str:
        """Return fully qualified name."""
        return f"{self.schema_name}.{self.name}"


@dataclass
class ColumnInfo:
    """Column metadata."""

    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    default_value: str | None = None


class MetadataService:
    """Service for database metadata introspection."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._connection_manager = connection_manager
        self._config = get_config()
        self._cache: dict[str, Any] = {}

    async def get_databases(self, connection_id: str) -> list[DatabaseInfo]:
        """Get list of databases for a connection."""
        connection = self._connection_manager.get_source_connection(connection_id)
        if connection is None:
            return []

        cache_key = f"{connection_id}:databases"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            result = await self._execute_metadata_query(
                connection, self._get_databases_query(connection.type), []
            )
            databases = [DatabaseInfo(name=row[0], schema_count=row[1] if len(row) > 1 else None) for row in result]
            self._cache[cache_key] = databases
            return databases
        except Exception as e:
            logger.warning(f"Failed to get databases for {connection_id}: {e}")
            return [DatabaseInfo(name=connection.database)]

    async def get_schemas(self, connection_id: str, database: str) -> list[SchemaInfo]:
        """Get list of schemas in a database."""
        connection = self._connection_manager.get_source_connection(connection_id)
        if connection is None:
            return []

        cache_key = f"{connection_id}:{database}:schemas"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            query, params = self._get_schemas_query(connection.type, database)
            result = await self._execute_metadata_query(connection, query, params)
            schemas = [SchemaInfo(name=row[0], table_count=row[1] if len(row) > 1 else None) for row in result]
            self._cache[cache_key] = schemas
            return schemas
        except Exception as e:
            logger.warning(f"Failed to get schemas for {connection_id}/{database}: {e}")
            return [SchemaInfo(name="public")]

    async def get_tables(
        self, connection_id: str, database: str, schema: str
    ) -> list[TableInfo]:
        """Get list of tables in a schema."""
        connection = self._connection_manager.get_source_connection(connection_id)
        if connection is None:
            return []

        cache_key = f"{connection_id}:{database}:{schema}:tables"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            query, params = self._get_tables_query(connection.type, database, schema)
            result = await self._execute_metadata_query(connection, query, params)
            tables = [
                TableInfo(
                    schema_name=schema,
                    name=row[0],
                    row_count=row[1] if len(row) > 1 else None,
                    table_type=row[2] if len(row) > 2 else "TABLE",
                )
                for row in result
            ]
            self._cache[cache_key] = tables
            return tables
        except Exception as e:
            logger.warning(f"Failed to get tables for {connection_id}/{database}/{schema}: {e}")
            return []

    async def get_columns(
        self, connection_id: str, database: str, schema: str, table: str
    ) -> list[ColumnInfo]:
        """Get columns for a table."""
        connection = self._connection_manager.get_source_connection(connection_id)
        if connection is None:
            return []

        cache_key = f"{connection_id}:{database}:{schema}:{table}:columns"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            query, params = self._get_columns_query(connection.type, database, schema, table)
            result = await self._execute_metadata_query(connection, query, params)
            columns = [
                ColumnInfo(
                    name=row[0],
                    data_type=row[1],
                    nullable=row[2] if len(row) > 2 else True,
                    is_primary_key=row[3] if len(row) > 3 else False,
                )
                for row in result
            ]
            self._cache[cache_key] = columns
            return columns
        except Exception as e:
            logger.warning(f"Failed to get columns for {connection_id}/{database}/{schema}/{table}: {e}")
            return []

    async def get_row_count(
        self, connection_id: str, database: str, schema: str, table: str
    ) -> int | None:
        """Get row count for a table."""
        connection = self._connection_manager.get_source_connection(connection_id)
        if connection is None:
            return None

        try:
            # Validate identifiers to prevent SQL injection
            safe_schema = _escape_identifier(schema)
            safe_table = _escape_identifier(table)

            # Use escaped identifiers (can't use parameters for identifiers)
            query = f'SELECT COUNT(*) FROM {safe_schema}.{safe_table}'
            result = await self._execute_metadata_query(connection, query, [])
            return result[0][0] if result else None
        except ValueError as e:
            logger.warning(f"Invalid identifier: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to get row count: {e}")
            return None

    async def get_sample_data(
        self, connection_id: str, database: str, schema: str, table: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get sample data from a table."""
        connection = self._connection_manager.get_source_connection(connection_id)
        if connection is None:
            return []

        try:
            columns = await self.get_columns(connection_id, database, schema, table)
            column_names = [c.name for c in columns]

            # Validate identifiers to prevent SQL injection
            safe_schema = _escape_identifier(schema)
            safe_table = _escape_identifier(table)

            # Validate limit is a reasonable number
            if not isinstance(limit, int) or limit < 1 or limit > 1000:
                limit = 10

            query = f'SELECT * FROM {safe_schema}.{safe_table} LIMIT {limit}'
            result = await self._execute_metadata_query(connection, query, [])
            return [dict(zip(column_names, row)) for row in result]
        except ValueError as e:
            logger.warning(f"Invalid identifier: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to get sample data: {e}")
            return []

    def clear_cache(self, connection_id: str | None = None) -> None:
        """Clear metadata cache."""
        if connection_id is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{connection_id}:")]
            for key in keys_to_remove:
                del self._cache[key]

    async def _execute_metadata_query(
        self, connection: SourceConnection, query: str, params: list
    ) -> list[tuple]:
        """Execute a metadata query with parameters."""
        timeout = self._config.performance.metadata_timeout_seconds

        def do_query() -> list[tuple]:
            import jaydebeapi

            driver_classes = {
                SourceType.POSTGRES: "org.postgresql.Driver",
                SourceType.MYSQL: "com.mysql.cj.jdbc.Driver",
                SourceType.ORACLE: "oracle.jdbc.driver.OracleDriver",
                SourceType.SQLSERVER: "com.microsoft.sqlserver.jdbc.SQLServerDriver",
            }

            driver_class = driver_classes.get(connection.type)
            conn = jaydebeapi.connect(
                driver_class or connection.jdbc_options.get("driver", ""),
                connection.jdbc_url,
                [connection.username, connection.password.get_secret_value()],
                connection.jdbc_options.get("jar_path"),
            )
            try:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                result = cursor.fetchall()
                cursor.close()
                return result
            finally:
                conn.close()

        return await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(None, do_query),
            timeout=timeout,
        )

    def _get_databases_query(self, source_type: SourceType) -> str:
        """Get database list query for source type."""
        queries = {
            SourceType.POSTGRES: """
                SELECT datname, NULL
                FROM pg_database
                WHERE datistemplate = false
                ORDER BY datname
            """,
            SourceType.MYSQL: """
                SELECT schema_name, NULL
                FROM information_schema.schemata
                ORDER BY schema_name
            """,
            SourceType.ORACLE: """
                SELECT username, NULL
                FROM all_users
                ORDER BY username
            """,
            SourceType.SQLSERVER: """
                SELECT name, NULL
                FROM sys.databases
                WHERE state = 0
                ORDER BY name
            """,
        }
        return queries.get(source_type, "SELECT 1")

    def _get_schemas_query(self, source_type: SourceType, database: str) -> tuple[str, list]:
        """Get schema list query for source type with parameters."""
        queries = {
            SourceType.POSTGRES: ("""
                SELECT schema_name, NULL
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY schema_name
            """, []),
            SourceType.MYSQL: ("""
                SELECT table_schema, COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = ?
                GROUP BY table_schema
                ORDER BY table_schema
            """, [database]),
            SourceType.ORACLE: ("""
                SELECT owner, COUNT(*)
                FROM all_tables
                GROUP BY owner
                ORDER BY owner
            """, []),
            SourceType.SQLSERVER: ("""
                SELECT schema_name, NULL
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest')
                ORDER BY schema_name
            """, []),
        }
        return queries.get(source_type, ("SELECT 'public', NULL", []))

    def _get_tables_query(
        self, source_type: SourceType, database: str, schema: str
    ) -> tuple[str, list]:
        """Get table list query for source type with parameters."""
        queries = {
            SourceType.POSTGRES: ("""
                SELECT
                    t.table_name,
                    NULL,
                    t.table_type
                FROM information_schema.tables t
                WHERE t.table_schema = ?
                ORDER BY t.table_name
            """, [schema]),
            SourceType.MYSQL: ("""
                SELECT table_name, table_rows, table_type
                FROM information_schema.tables
                WHERE table_schema = ?
                ORDER BY table_name
            """, [database]),
            SourceType.ORACLE: ("""
                SELECT table_name, num_rows, 'TABLE'
                FROM all_tables
                WHERE owner = ?
                ORDER BY table_name
            """, [schema]),
            SourceType.SQLSERVER: ("""
                SELECT t.name, SUM(p.rows), 'TABLE'
                FROM sys.tables t
                JOIN sys.partitions p ON t.object_id = p.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE s.name = ? AND p.index_id IN (0, 1)
                GROUP BY t.name
                ORDER BY t.name
            """, [schema]),
        }
        return queries.get(source_type, ("SELECT 'unknown', NULL, 'TABLE'", []))

    def _get_columns_query(
        self, source_type: SourceType, database: str, schema: str, table: str
    ) -> tuple[str, list]:
        """Get column list query for source type with parameters."""
        queries = {
            SourceType.POSTGRES: ("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable = 'YES',
                    FALSE
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = ?
                ORDER BY ordinal_position
            """, [schema, table]),
            SourceType.MYSQL: ("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable = 'YES',
                    column_key = 'PRI'
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = ?
                ORDER BY ordinal_position
            """, [database, table]),
            SourceType.ORACLE: ("""
                SELECT
                    column_name,
                    data_type,
                    nullable = 'Y',
                    0
                FROM all_tab_columns
                WHERE owner = ? AND table_name = ?
                ORDER BY column_id
            """, [schema, table]),
            SourceType.SQLSERVER: ("""
                SELECT
                    c.name,
                    t.name,
                    c.is_nullable,
                    ISNULL(i.is_primary_key, 0)
                FROM sys.columns c
                JOIN sys.types t ON c.user_type_id = t.user_type_id
                JOIN sys.tables tb ON c.object_id = tb.object_id
                JOIN sys.schemas s ON tb.schema_id = s.schema_id
                LEFT JOIN sys.index_columns ic ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                LEFT JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                WHERE s.name = ? AND tb.name = ?
                ORDER BY c.column_id
            """, [schema, table]),
        }
        return queries.get(source_type, ("SELECT 'id', 'integer', true, true FROM dual", []))
