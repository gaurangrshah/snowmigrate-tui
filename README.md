# SnowMigrate TUI

Terminal-based user interface for managing data migrations to Snowflake using an existing PySpark-based migration engine.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
  - [Connection Management](#connection-management)
  - [Source Browser](#source-browser)
  - [Staging Areas](#staging-areas)
  - [Migration Configuration](#migration-configuration)
  - [WAR Room Dashboard](#war-room-dashboard)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Configuration File](#configuration-file)
- [Integration](#integration)
  - [Migration Engine Integration](#migration-engine-integration)
  - [Database Connectivity](#database-connectivity)
  - [Staging Area Setup](#staging-area-setup)
- [Maintenance](#maintenance)
  - [Logs and Monitoring](#logs-and-monitoring)
  - [Troubleshooting](#troubleshooting)
  - [Updating](#updating)
- [Development](#development)
- [Architecture](#architecture)
- [License](#license)

---

## Features

- **Connection Management**: Configure and test source database and Snowflake connections
- **Source Browser**: Navigate database schemas and select tables for migration
- **Staging Area Selection**: Choose S3, Azure Blob, or GCS staging locations
- **Migration Monitoring**: Real-time progress tracking with WAR room dashboard
- **Concurrent Operations**: Monitor 10+ simultaneous migrations
- **Keyboard-Driven**: Full keyboard navigation for efficient operation

---

## Installation

### From PyPI (when published)

```bash
pip install snowmigrate-tui
```

### From Source

```bash
git clone https://github.com/gaurangrshah/snowmigrate-tui.git
cd snowmigrate-tui
pip install -e .
```

### Requirements

- Python 3.10+
- Linux/macOS terminal with 256+ colors
- Network access to source databases and Snowflake
- JDBC drivers for source databases (see [Database Connectivity](#database-connectivity))

---

## Quick Start

1. **Launch the application:**
   ```bash
   snowmigrate
   ```

2. **Add a source connection** (Connections tab → Add Source)

3. **Add a Snowflake connection** (Connections tab → Add Snowflake)

4. **Browse and select tables** (Browser tab)

5. **Configure and start migration** (Dashboard tab)

---

## Usage Guide

### Connection Management

#### Adding a Source Connection

1. Navigate to **Connections** tab
2. Click **Add Source** or press `a`
3. Fill in connection details:
   - **Name**: Friendly identifier (e.g., "Production MySQL")
   - **Type**: postgres, mysql, oracle, sqlserver, or db2
   - **Host**: Database server hostname or IP
   - **Port**: Database port (defaults provided per type)
   - **Database**: Database/schema name
   - **Username/Password**: Credentials

4. Click **Test Connection** to verify
5. Click **Save** to store

#### Adding a Snowflake Connection

1. Navigate to **Connections** tab
2. Click **Add Snowflake** or press `s`
3. Fill in connection details:
   - **Name**: Friendly identifier
   - **Account**: Snowflake account identifier (e.g., `xy12345.us-east-1`)
   - **Warehouse**: Compute warehouse name
   - **Database**: Target database
   - **Schema**: Target schema (default: `PUBLIC`)
   - **Username/Password**: Credentials
   - **Role** (optional): Snowflake role

4. Test and save

#### Connection Status Indicators

| Indicator | Meaning |
|-----------|---------|
| `[OK]` | Connection verified |
| `[FAIL]` | Connection failed (see error) |
| `[...]` | Testing in progress |
| `[?]` | Not yet tested |

---

### Source Browser

The Source Browser displays your source database structure in a navigable tree.

#### Navigation

| Key | Action |
|-----|--------|
| `↑/↓` | Move selection |
| `Enter` | Expand/collapse node |
| `Space` | Toggle table selection |
| `a` | Select all tables in schema |
| `n` | Deselect all |
| `r` | Refresh metadata |

#### Tree Structure

```
└── source_connection_name
    └── schema_name
        ├── [x] table_1 (1,234 rows)
        ├── [ ] table_2 (5,678 rows)
        └── [x] table_3 (910 rows)
```

- Checkboxes indicate selection status
- Row counts shown when available
- Schemas are expandable/collapsible

---

### Staging Areas

Staging areas are intermediate storage locations used during migration.

#### Supported Types

| Type | Description |
|------|-------------|
| S3 | Amazon S3 bucket |
| Azure | Azure Blob Storage container |
| GCS | Google Cloud Storage bucket |
| Local | Local filesystem (dev only) |

#### Selecting a Staging Area

1. In migration configuration, select from available staging areas
2. Ensure the staging area is marked `[OK]` (accessible)
3. The path shows where intermediate files will be stored

---

### Migration Configuration

#### Creating a Migration

1. Select tables in the **Browser** tab
2. Navigate to **Dashboard** tab
3. Click **New Migration** or press `n`
4. Configure:
   - **Source**: Pre-selected from browser
   - **Target**: Choose Snowflake connection
   - **Staging**: Select staging area
   - **Tables**: Review selected tables
   - **Options**:
     - Truncate target tables before load
     - Preserve existing data (append mode)
     - Include row counts verification

5. Click **Start Migration**

#### Migration Options

| Option | Description |
|--------|-------------|
| `--truncate` | Clear target tables before loading |
| `--verify-counts` | Compare row counts after migration |
| `--parallel N` | Max parallel table migrations |

---

### WAR Room Dashboard

The WAR (Watch, Analyze, React) Room provides real-time monitoring of all migrations.

#### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  Active: 3    Queued: 5    Completed: 12    Failed: 1  │
├─────────────────────────────────────────────────────┤
│  Migration: prod-to-snowflake-001                    │
│  Status: RUNNING   Progress: 67% (8/12 tables)       │
│  ████████████████████░░░░░░░░░░  Current: orders     │
├─────────────────────────────────────────────────────┤
│  Migration: prod-to-snowflake-002                    │
│  Status: QUEUED    Progress: 0% (0/5 tables)         │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Waiting...          │
└─────────────────────────────────────────────────────┘
```

#### Status Indicators

| Status | Color | Meaning |
|--------|-------|---------|
| QUEUED | Gray | Waiting to start |
| RUNNING | Blue | In progress |
| COMPLETED | Green | Finished successfully |
| FAILED | Red | Error occurred |
| PAUSED | Yellow | Manually paused |

#### Keyboard Controls

| Key | Action |
|-----|--------|
| `p` | Pause selected migration |
| `r` | Resume paused migration |
| `c` | Cancel migration |
| `l` | View logs |
| `d` | View details |
| `↑/↓` | Navigate migrations |

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SNOWMIGRATE_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `SNOWMIGRATE_CLI_PATH` | Path to migration CLI executable | Auto-detect |
| `SNOWMIGRATE_MAX_CONCURRENT` | Maximum concurrent migrations | `10` |
| `SNOWMIGRATE_CONFIG_FILE` | Path to config file | `~/.snowmigrate/config.toml` |

#### Connection-Specific Variables

For automated/CI usage, connections can be configured via environment:

```bash
# Source connection
export SNOWMIGRATE_SOURCE_HOST=mydb.example.com
export SNOWMIGRATE_SOURCE_PORT=5432
export SNOWMIGRATE_SOURCE_DATABASE=production
export SNOWMIGRATE_SOURCE_USERNAME=readonly
export SNOWMIGRATE_SOURCE_PASSWORD=secret

# Snowflake connection
export SNOWMIGRATE_SF_ACCOUNT=xy12345.us-east-1
export SNOWMIGRATE_SF_WAREHOUSE=COMPUTE_WH
export SNOWMIGRATE_SF_DATABASE=RAW
export SNOWMIGRATE_SF_USERNAME=loader
export SNOWMIGRATE_SF_PASSWORD=secret
```

### Configuration File

Create `~/.snowmigrate/config.toml`:

```toml
[app]
log_level = "INFO"

[cli]
path = "/usr/local/bin/snowmigrate-cli"
timeout_seconds = 3600

[performance]
max_concurrent_migrations = 10
progress_poll_interval_ms = 1000
metadata_timeout_seconds = 30
connection_test_timeout_seconds = 10

[ui]
theme = "dark"
show_row_counts = true
sample_data_rows = 10
```

---

## Integration

### Migration Engine Integration

SnowMigrate TUI wraps an existing PySpark-based migration CLI. Configure the CLI path:

```bash
export SNOWMIGRATE_CLI_PATH=/path/to/migration-cli
```

#### Expected CLI Interface

The TUI expects the migration CLI to accept:

```bash
migration-cli migrate \
  --source-type postgres \
  --source-host dbhost \
  --source-port 5432 \
  --source-database mydb \
  --source-user readonly \
  --target-account xy12345.us-east-1 \
  --target-warehouse COMPUTE_WH \
  --target-database RAW \
  --target-schema PUBLIC \
  --target-user loader \
  --staging-path s3://bucket/staging \
  --tables public.users,public.orders
```

Credentials are passed via environment variables:
- `SNOWMIGRATE_SOURCE_PASSWORD`
- `SNOWMIGRATE_TARGET_PASSWORD`

#### CLI Output Parsing

The TUI parses CLI output for progress updates. Expected format:

```
[INFO] Starting migration of table: public.users
[PROGRESS] public.users: 50% (500000/1000000 rows)
[INFO] Completed migration of table: public.users
[ERROR] Failed to migrate public.orders: Connection timeout
```

### Database Connectivity

#### JDBC Drivers

Place JDBC drivers in `~/.snowmigrate/drivers/` or set:

```bash
export SNOWMIGRATE_JDBC_DRIVERS=/path/to/drivers
```

Required drivers by database type:

| Database | Driver JAR |
|----------|------------|
| PostgreSQL | `postgresql-42.x.x.jar` |
| MySQL | `mysql-connector-java-8.x.x.jar` |
| Oracle | `ojdbc8.jar` |
| SQL Server | `mssql-jdbc-9.x.x.jar` |
| DB2 | `jcc.jar` |

#### Connection String Formats

| Type | Format |
|------|--------|
| PostgreSQL | `jdbc:postgresql://host:port/database` |
| MySQL | `jdbc:mysql://host:port/database` |
| Oracle | `jdbc:oracle:thin:@host:port:SID` |
| SQL Server | `jdbc:sqlserver://host:port;databaseName=db` |
| DB2 | `jdbc:db2://host:port/database` |

### Staging Area Setup

#### Amazon S3

1. Create S3 bucket for staging
2. Configure AWS credentials:
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_REGION=us-east-1
   ```
3. Ensure Snowflake has access (storage integration or direct credentials)

#### Azure Blob Storage

1. Create storage container
2. Configure Azure credentials:
   ```bash
   export AZURE_STORAGE_ACCOUNT=account_name
   export AZURE_STORAGE_KEY=your_key
   ```

#### Google Cloud Storage

1. Create GCS bucket
2. Configure GCP credentials:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   ```

---

## Maintenance

### Logs and Monitoring

#### Log Locations

| Log | Location |
|-----|----------|
| Application log | `~/.snowmigrate/logs/app.log` |
| Migration logs | `~/.snowmigrate/logs/migrations/` |
| CLI output | `~/.snowmigrate/logs/cli/` |

#### Log Levels

Set via `SNOWMIGRATE_LOG_LEVEL`:

- `DEBUG`: Verbose, includes SQL queries
- `INFO`: Standard operational logs
- `WARNING`: Potential issues
- `ERROR`: Failures only

#### Viewing Logs in TUI

Press `l` on any migration to view real-time logs in a scrollable pane.

### Troubleshooting

#### Common Issues

| Issue | Solution |
|-------|----------|
| Connection timeout | Check network/firewall, increase `connection_test_timeout_seconds` |
| "No JDBC driver found" | Install driver in `~/.snowmigrate/drivers/` |
| Migration stuck at 0% | Check CLI path, verify CLI works standalone |
| "Permission denied" on staging | Verify cloud credentials and bucket permissions |
| High memory usage | Reduce `max_concurrent_migrations` |

#### Resetting State

```bash
# Clear all saved connections (caution!)
rm -rf ~/.snowmigrate/connections/

# Clear migration history
rm -rf ~/.snowmigrate/migrations/

# Reset to defaults
rm ~/.snowmigrate/config.toml
```

#### Debug Mode

Run with verbose logging:

```bash
SNOWMIGRATE_LOG_LEVEL=DEBUG snowmigrate
```

### Updating

#### From PyPI

```bash
pip install --upgrade snowmigrate-tui
```

#### From Source

```bash
cd snowmigrate-tui
git pull origin main
pip install -e .
```

---

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/gaurangrshah/snowmigrate-tui.git
cd snowmigrate-tui

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=snowmigrate --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
ruff format src/
```

### Project Structure

```
snowmigrate-tui/
├── src/snowmigrate/
│   ├── __init__.py
│   ├── app.py              # Main Textual application
│   ├── config.py           # Configuration management
│   ├── models/             # Pydantic data models
│   │   ├── connection.py   # Connection models
│   │   ├── migration.py    # Migration models
│   │   └── staging.py      # Staging area models
│   ├── services/           # Business logic
│   │   ├── connection_manager.py
│   │   ├── metadata_service.py
│   │   └── migration_engine.py
│   ├── screens/            # TUI screens
│   │   ├── connections.py
│   │   ├── browser.py
│   │   ├── dashboard.py
│   │   └── migration_config.py
│   ├── widgets/            # Reusable TUI components
│   │   ├── connection_card.py
│   │   ├── migration_row.py
│   │   └── staging_selector.py
│   └── styles.tcss         # Textual CSS styles
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_config.py
├── pyproject.toml
└── README.md
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make changes with tests
4. Run linting: `ruff check src/`
5. Submit a pull request

---

## Architecture

### Technology Stack

| Component | Technology |
|-----------|------------|
| TUI Framework | [Textual](https://textual.textualize.io/) 1.0+ |
| Data Validation | [Pydantic](https://docs.pydantic.dev/) 2.0+ |
| Database Connectivity | [JayDeBeApi](https://github.com/baztian/jaydebeapi) |
| Async Operations | Python asyncio |
| Styling | Textual CSS (TCSS) |

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Source    │────▶│   Staging    │────▶│  Snowflake  │
│  Database   │     │   (S3/etc)   │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────┐
│              Migration CLI (PySpark)                 │
└─────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────┐
│              SnowMigrate TUI (this app)             │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐       │
│  │Connections│  │  Browser  │  │ Dashboard │       │
│  └───────────┘  └───────────┘  └───────────┘       │
└─────────────────────────────────────────────────────┘
```

### Security Considerations

- Passwords stored using Pydantic `SecretStr` (never logged)
- Credentials passed to CLI via environment variables (not command line)
- SQL queries use parameterized statements (no injection)
- Connection strings validated before use

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/gaurangrshah/snowmigrate-tui/issues)
- **Discussions**: [GitHub Discussions](https://github.com/gaurangrshah/snowmigrate-tui/discussions)
