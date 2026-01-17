# SnowMigrate TUI

Terminal-based user interface for managing data migrations to Snowflake using an existing PySpark-based migration engine.

## Features

- **Connection Management**: Configure and test source database and Snowflake connections
- **Source Browser**: Navigate database schemas and select tables for migration
- **Migration Monitoring**: Real-time progress tracking with WAR room dashboard
- **Concurrent Operations**: Monitor 10+ simultaneous migrations

## Requirements

- Python 3.10+
- Linux terminal with 256+ colors
- Access to source databases and Snowflake

## Installation

```bash
pip install snowmigrate-tui
```

## Usage

```bash
snowmigrate
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

MIT
