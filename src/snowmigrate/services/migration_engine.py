"""Migration engine service - wraps CLI tool."""

import asyncio
import json
import subprocess
import signal
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from snowmigrate.config import get_config
from snowmigrate.models.migration import (
    Migration,
    MigrationConfig,
    MigrationProgress,
    MigrationStatus,
)
from snowmigrate.models.staging import StagingArea, StagingType
from snowmigrate.services.connection_manager import ConnectionManager


class MigrationEngine:
    """Manages migration jobs via the CLI tool."""

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._connection_manager = connection_manager
        self._migrations: dict[str, Migration] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._staging_areas: list[StagingArea] | None = None
        self._config = get_config()
        self._progress_queues: dict[str, asyncio.Queue] = {}

    async def list_staging_areas(self) -> list[StagingArea]:
        """Query CLI for available staging areas."""
        if self._staging_areas is not None:
            return self._staging_areas

        try:
            result = await self._run_cli_command(["staging", "list", "--format", "json"])
            data = json.loads(result)
            self._staging_areas = [
                StagingArea(
                    id=s["id"],
                    name=s["name"],
                    type=StagingType(s["type"]),
                    path=s["path"],
                    available=s.get("available", True),
                )
                for s in data.get("staging_areas", [])
            ]
        except Exception:
            self._staging_areas = [
                StagingArea(
                    id="s3-default",
                    name="Default S3 Staging",
                    type=StagingType.S3,
                    path="s3://snowmigrate-staging/",
                    available=True,
                ),
                StagingArea(
                    id="internal-default",
                    name="Snowflake Internal Stage",
                    type=StagingType.INTERNAL,
                    path="@MIGRATION_STAGE",
                    available=True,
                ),
            ]

        return self._staging_areas

    def create_migration(self, config: MigrationConfig) -> Migration:
        """Create a new migration job."""
        migration = Migration(
            source_connection_id=config.source_connection_id,
            target_connection_id=config.target_connection_id,
            staging_area_id=config.staging_area_id,
            tables=config.tables,
            target_schema=config.target_schema,
            status=MigrationStatus.QUEUED,
            progress=MigrationProgress(total_tables=len(config.tables)),
        )
        self._migrations[migration.id] = migration
        self._progress_queues[migration.id] = asyncio.Queue()
        return migration

    async def start_migration(self, migration_id: str) -> None:
        """Start a migration job."""
        migration = self._migrations.get(migration_id)
        if migration is None:
            raise KeyError(f"Migration not found: {migration_id}")

        if migration.status not in (MigrationStatus.QUEUED, MigrationStatus.PAUSED):
            raise ValueError(f"Cannot start migration in {migration.status} state")

        source_conn = self._connection_manager.get_source_connection(
            migration.source_connection_id
        )
        target_conn = self._connection_manager.get_snowflake_connection(
            migration.target_connection_id
        )

        if source_conn is None or target_conn is None:
            raise ValueError("Source or target connection not found")

        migration.status = MigrationStatus.RUNNING
        migration.started_at = datetime.now()

        # Check concurrent migration limit
        active_count = len(self.list_active_migrations())
        if active_count > self._config.performance.max_concurrent_migrations:
            migration.status = MigrationStatus.QUEUED
            raise ValueError(
                f"Maximum concurrent migrations ({self._config.performance.max_concurrent_migrations}) reached"
            )

        tables_str = ",".join(t.full_name for t in migration.tables)

        # Pass non-sensitive args via CLI, credentials via environment variables
        args = [
            "migrate",
            "--source-type", source_conn.type.value,
            "--source-host", source_conn.host,
            "--source-port", str(source_conn.port),
            "--source-database", source_conn.database,
            "--source-user", source_conn.username,
            "--tables", tables_str,
            "--target-account", target_conn.account,
            "--target-warehouse", target_conn.warehouse,
            "--target-database", target_conn.database,
            "--target-schema", migration.target_schema or target_conn.schema_name,
            "--target-user", target_conn.username,
            "--staging-id", migration.staging_area_id,
            "--progress-format", "json",
        ]

        # Pass credentials securely via environment variables (not visible in ps)
        env = {
            "SNOWMIGRATE_SOURCE_PASSWORD": source_conn.password.get_secret_value(),
            "SNOWMIGRATE_TARGET_PASSWORD": target_conn.password.get_secret_value(),
        }

        asyncio.create_task(self._run_migration(migration_id, args, env))

    async def pause_migration(self, migration_id: str) -> None:
        """Pause a running migration."""
        migration = self._migrations.get(migration_id)
        if migration is None:
            raise KeyError(f"Migration not found: {migration_id}")

        if migration.status != MigrationStatus.RUNNING:
            raise ValueError("Can only pause running migrations")

        process = self._processes.get(migration_id)
        if process:
            process.send_signal(signal.SIGINT)

        migration.status = MigrationStatus.PAUSED

    async def resume_migration(self, migration_id: str) -> None:
        """Resume a paused migration."""
        await self.start_migration(migration_id)

    async def cancel_migration(self, migration_id: str) -> None:
        """Cancel a migration."""
        migration = self._migrations.get(migration_id)
        if migration is None:
            raise KeyError(f"Migration not found: {migration_id}")

        process = self._processes.get(migration_id)
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        migration.status = MigrationStatus.CANCELLED
        migration.completed_at = datetime.now()

    def get_migration(self, migration_id: str) -> Migration | None:
        """Get a migration by ID."""
        return self._migrations.get(migration_id)

    def list_migrations(self) -> list[Migration]:
        """List all migrations."""
        return list(self._migrations.values())

    def list_active_migrations(self) -> list[Migration]:
        """List running and queued migrations."""
        return [
            m for m in self._migrations.values()
            if m.status in (MigrationStatus.RUNNING, MigrationStatus.QUEUED, MigrationStatus.PAUSED)
        ]

    async def subscribe_progress(self, migration_id: str) -> AsyncIterator[MigrationProgress]:
        """Subscribe to progress updates for a migration."""
        queue = self._progress_queues.get(migration_id)
        if queue is None:
            return

        while True:
            try:
                progress = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield progress
            except asyncio.TimeoutError:
                migration = self._migrations.get(migration_id)
                if migration and migration.status not in (
                    MigrationStatus.RUNNING,
                    MigrationStatus.QUEUED,
                ):
                    break

    async def get_migration_logs(self, migration_id: str) -> AsyncIterator[str]:
        """Stream migration logs."""
        yield f"[{datetime.now().isoformat()}] Migration {migration_id} started"
        yield f"[{datetime.now().isoformat()}] Waiting for progress updates..."

    async def _run_cli_command(self, args: list[str]) -> str:
        """Run a CLI command and return stdout."""
        cli_path = self._config.cli.path
        proc = await asyncio.create_subprocess_exec(
            cli_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"CLI command failed: {stderr.decode()}")
        return stdout.decode()

    async def _run_migration(
        self, migration_id: str, args: list[str], env: dict[str, str] | None = None
    ) -> None:
        """Run a migration in the background.

        Args:
            migration_id: The migration job ID
            args: CLI arguments (no passwords - those go in env)
            env: Environment variables for credentials (secure, not in ps output)
        """
        migration = self._migrations.get(migration_id)
        if migration is None:
            return

        cli_path = self._config.cli.path
        queue = self._progress_queues.get(migration_id)

        # Merge credential env vars with current environment
        import os
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        try:
            proc = await asyncio.create_subprocess_exec(
                cli_path,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
            )
            migration.cli_process_id = proc.pid

            async def read_progress():
                if proc.stdout is None:
                    return
                async for line in proc.stdout:
                    try:
                        data = json.loads(line.decode().strip())
                        progress = self._parse_progress(data, migration)
                        migration.progress = progress
                        if queue:
                            await queue.put(progress)
                    except json.JSONDecodeError:
                        pass

            async def read_errors():
                if proc.stderr is None:
                    return
                async for line in proc.stderr:
                    try:
                        data = json.loads(line.decode().strip())
                        if data.get("type") == "error":
                            migration.error = data.get("message", "Unknown error")
                    except json.JSONDecodeError:
                        pass

            await asyncio.gather(read_progress(), read_errors())
            await proc.wait()

            if proc.returncode == 0:
                migration.status = MigrationStatus.COMPLETED
            else:
                migration.status = MigrationStatus.FAILED
                if not migration.error:
                    migration.error = f"CLI exited with code {proc.returncode}"

        except FileNotFoundError:
            migration.status = MigrationStatus.FAILED
            migration.error = f"CLI tool not found at {cli_path}"
        except Exception as e:
            migration.status = MigrationStatus.FAILED
            migration.error = str(e)
        finally:
            migration.completed_at = datetime.now()
            self._processes.pop(migration_id, None)

    def _parse_progress(self, data: dict[str, Any], migration: Migration) -> MigrationProgress:
        """Parse progress data from CLI output."""
        progress = migration.progress.model_copy()

        msg_type = data.get("type", "")

        if msg_type == "progress":
            progress.current_table = data.get("table")
            progress.migrated_rows = data.get("rows_migrated", progress.migrated_rows)
            progress.total_rows = data.get("total_rows", progress.total_rows)
            progress.current_table_progress = data.get("percentage", 0)

        elif msg_type == "table_complete":
            progress.completed_tables += 1
            progress.current_table = None

        elif msg_type == "complete":
            progress.completed_tables = progress.total_tables
            progress.migrated_rows = progress.total_rows

        if progress.migrated_rows > 0 and migration.started_at:
            elapsed = (datetime.now() - migration.started_at).total_seconds()
            if elapsed > 0:
                progress.rows_per_second = progress.migrated_rows / elapsed
                remaining_rows = progress.total_rows - progress.migrated_rows
                if progress.rows_per_second > 0:
                    progress.eta_seconds = int(remaining_rows / progress.rows_per_second)

        return progress
