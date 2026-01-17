"""Connection lifecycle management service."""

import asyncio
import time
from datetime import datetime

from snowmigrate.config import get_config
from snowmigrate.models.connection import (
    ConnectionStatus,
    ConnectionTestResult,
    SnowflakeConnection,
    SourceConnection,
    SourceType,
)


class ConnectionManager:
    """Manages source and target database connections."""

    def __init__(self) -> None:
        self._source_connections: dict[str, SourceConnection] = {}
        self._snowflake_connections: dict[str, SnowflakeConnection] = {}
        self._config = get_config()

    def add_source_connection(self, connection: SourceConnection) -> str:
        """Add a new source connection."""
        self._source_connections[connection.id] = connection
        return connection.id

    def add_snowflake_connection(self, connection: SnowflakeConnection) -> str:
        """Add a new Snowflake connection."""
        self._snowflake_connections[connection.id] = connection
        return connection.id

    def update_source_connection(self, connection_id: str, connection: SourceConnection) -> None:
        """Update an existing source connection."""
        if connection_id not in self._source_connections:
            raise KeyError(f"Source connection not found: {connection_id}")
        connection.id = connection_id
        self._source_connections[connection_id] = connection

    def update_snowflake_connection(
        self, connection_id: str, connection: SnowflakeConnection
    ) -> None:
        """Update an existing Snowflake connection."""
        if connection_id not in self._snowflake_connections:
            raise KeyError(f"Snowflake connection not found: {connection_id}")
        connection.id = connection_id
        self._snowflake_connections[connection_id] = connection

    def delete_source_connection(self, connection_id: str) -> None:
        """Delete a source connection."""
        if connection_id in self._source_connections:
            del self._source_connections[connection_id]

    def delete_snowflake_connection(self, connection_id: str) -> None:
        """Delete a Snowflake connection."""
        if connection_id in self._snowflake_connections:
            del self._snowflake_connections[connection_id]

    def get_source_connection(self, connection_id: str) -> SourceConnection | None:
        """Get a source connection by ID."""
        return self._source_connections.get(connection_id)

    def get_snowflake_connection(self, connection_id: str) -> SnowflakeConnection | None:
        """Get a Snowflake connection by ID."""
        return self._snowflake_connections.get(connection_id)

    def list_source_connections(self) -> list[SourceConnection]:
        """List all source connections."""
        return list(self._source_connections.values())

    def list_snowflake_connections(self) -> list[SnowflakeConnection]:
        """List all Snowflake connections."""
        return list(self._snowflake_connections.values())

    async def test_source_connection(self, connection_id: str) -> ConnectionTestResult:
        """Test a source database connection."""
        connection = self._source_connections.get(connection_id)
        if connection is None:
            return ConnectionTestResult(success=False, message="Connection not found")

        connection.status = ConnectionStatus.TESTING
        start_time = time.monotonic()

        try:
            result = await self._test_jdbc_connection(connection)
            connection.status = (
                ConnectionStatus.CONNECTED if result.success else ConnectionStatus.FAILED
            )
            connection.last_tested = datetime.now()
            connection.error_message = None if result.success else result.message
            return result
        except Exception as e:
            connection.status = ConnectionStatus.FAILED
            connection.last_tested = datetime.now()
            connection.error_message = str(e)
            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {e}",
                latency_ms=(time.monotonic() - start_time) * 1000,
            )

    async def test_snowflake_connection(self, connection_id: str) -> ConnectionTestResult:
        """Test a Snowflake connection."""
        connection = self._snowflake_connections.get(connection_id)
        if connection is None:
            return ConnectionTestResult(success=False, message="Connection not found")

        connection.status = ConnectionStatus.TESTING
        start_time = time.monotonic()

        try:
            result = await self._test_snowflake(connection)
            connection.status = (
                ConnectionStatus.CONNECTED if result.success else ConnectionStatus.FAILED
            )
            connection.last_tested = datetime.now()
            connection.error_message = None if result.success else result.message
            return result
        except Exception as e:
            connection.status = ConnectionStatus.FAILED
            connection.last_tested = datetime.now()
            connection.error_message = str(e)
            return ConnectionTestResult(
                success=False,
                message=f"Connection test failed: {e}",
                latency_ms=(time.monotonic() - start_time) * 1000,
            )

    async def _test_jdbc_connection(self, connection: SourceConnection) -> ConnectionTestResult:
        """Test a JDBC connection using jaydebeapi."""
        timeout = self._config.performance.connection_test_timeout_seconds
        start_time = time.monotonic()

        try:
            driver_classes = {
                SourceType.POSTGRES: "org.postgresql.Driver",
                SourceType.MYSQL: "com.mysql.cj.jdbc.Driver",
                SourceType.ORACLE: "oracle.jdbc.driver.OracleDriver",
                SourceType.SQLSERVER: "com.microsoft.sqlserver.jdbc.SQLServerDriver",
            }

            driver_class = driver_classes.get(connection.type)
            if driver_class is None and connection.type != SourceType.JDBC:
                return ConnectionTestResult(
                    success=False,
                    message=f"Unsupported database type: {connection.type}",
                )

            def do_test() -> ConnectionTestResult:
                import jaydebeapi

                conn = jaydebeapi.connect(
                    driver_class or connection.jdbc_options.get("driver", ""),
                    connection.jdbc_url,
                    [connection.username, connection.password.get_secret_value()],
                    connection.jdbc_options.get("jar_path"),
                )
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.close()

                    latency = (time.monotonic() - start_time) * 1000
                    return ConnectionTestResult(
                        success=True,
                        message="Connection successful",
                        latency_ms=latency,
                    )
                finally:
                    conn.close()

            result = await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(None, do_test),
                timeout=timeout,
            )
            return result

        except asyncio.TimeoutError:
            return ConnectionTestResult(
                success=False,
                message=f"Connection timed out after {timeout} seconds",
                latency_ms=timeout * 1000,
            )
        except ImportError:
            return ConnectionTestResult(
                success=False,
                message="jaydebeapi not installed. Install with: pip install jaydebeapi",
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=str(e),
                latency_ms=(time.monotonic() - start_time) * 1000,
            )

    async def _test_snowflake(self, connection: SnowflakeConnection) -> ConnectionTestResult:
        """Test Snowflake connection using snowflake-connector-python."""
        timeout = self._config.performance.connection_test_timeout_seconds
        start_time = time.monotonic()

        try:

            def do_test() -> ConnectionTestResult:
                try:
                    import snowflake.connector

                    conn = snowflake.connector.connect(
                        account=connection.account,
                        user=connection.username,
                        password=connection.password.get_secret_value(),
                        warehouse=connection.warehouse,
                        database=connection.database,
                        schema=connection.schema_name,
                        role=connection.role,
                    )
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT CURRENT_VERSION()")
                        version = cursor.fetchone()
                        cursor.close()

                        latency = (time.monotonic() - start_time) * 1000
                        return ConnectionTestResult(
                            success=True,
                            message="Connection successful",
                            latency_ms=latency,
                            server_version=version[0] if version else None,
                        )
                    finally:
                        conn.close()
                except ImportError:
                    return ConnectionTestResult(
                        success=False,
                        message="snowflake-connector-python not installed",
                    )

            result = await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(None, do_test),
                timeout=timeout,
            )
            return result

        except asyncio.TimeoutError:
            return ConnectionTestResult(
                success=False,
                message=f"Connection timed out after {timeout} seconds",
                latency_ms=timeout * 1000,
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=str(e),
                latency_ms=(time.monotonic() - start_time) * 1000,
            )
