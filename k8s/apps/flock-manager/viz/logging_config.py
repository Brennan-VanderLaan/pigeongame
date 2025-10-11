"""
Centralized logging configuration for mesh network application.

This module provides structured logging suitable for ELK stack ingestion with:
- JSON formatted logs for machine readability
- Timestamp, source file, line number, and message
- Configurable log levels
- Separation of application logs (stderr) from output (stdout)
- SQL logs directed to stderr to keep stdout clean
"""

import logging
import logging.config
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Outputs logs in a format suitable for ELK stack ingestion:
    {
        "timestamp": "2025-09-30T08:45:30.123456Z",
        "level": "INFO",
        "logger": "mesh_cli",
        "source": "mesh_cli.py:123",
        "message": "Mesh created successfully",
        "extra": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        # Create base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "source": f"{Path(record.pathname).name}:{record.lineno}",
            "message": record.getMessage()
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'exc_info', 'exc_text', 'stack_info'):
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry)


class PlainFormatter(logging.Formatter):
    """
    Plain text formatter for development and console output.

    Format: 2025-09-30T08:45:30.123Z [INFO] mesh_cli.py:123 - Mesh created successfully
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
        source = f"{Path(record.pathname).name}:{record.lineno}"

        formatted = f"{timestamp} [{record.levelname}] {source} - {record.getMessage()}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    log_file: str = None,
    silence_sql: bool = True
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "json" for structured logs, "plain" for human-readable
        log_file: Optional file path for log output
        silence_sql: If True, suppress SQLAlchemy logs or send to stderr only
    """

    # Choose formatter
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = PlainFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Stderr handler for application logs (not stdout to keep output clean)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(level.upper())
    root_logger.addHandler(stderr_handler)

    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level.upper())
        root_logger.addHandler(file_handler)

    # Configure SQLAlchemy logging
    if silence_sql:
        # Completely silence SQLAlchemy logs in production
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    else:
        # In debug mode, allow SQL logs but ensure they go to stderr
        sql_logger = logging.getLogger("sqlalchemy.engine")
        sql_logger.setLevel(logging.INFO)
        # SQL logs will use the stderr handler we already configured


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module/component.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def setup_cli_logging(verbose: int = 0, quiet: bool = False) -> None:
    """
    Setup logging specifically for CLI usage.

    Args:
        verbose: Verbosity level (0=INFO, 1=DEBUG, 2=DEBUG with SQL)
        quiet: If True, suppress all logs except ERROR
    """
    if quiet:
        level = "ERROR"
        silence_sql = True
    elif verbose >= 2:
        level = "DEBUG"
        silence_sql = False  # Show SQL logs in debug mode
    elif verbose >= 1:
        level = "DEBUG"
        silence_sql = True
    else:
        level = "INFO"
        silence_sql = True

    configure_logging(
        level=level,
        format_type="plain",  # Human readable for CLI
        silence_sql=silence_sql
    )


def setup_web_logging(log_file: str = None) -> None:
    """
    Setup logging for web application (structured JSON logs).

    Args:
        log_file: Optional log file path
    """
    configure_logging(
        level="INFO",
        format_type="json",  # Structured for ELK stack
        log_file=log_file,
        silence_sql=True  # Keep SQL noise out of application logs
    )


def setup_test_logging() -> None:
    """
    Setup minimal logging for tests.
    """
    configure_logging(
        level="WARNING",  # Only show warnings and errors in tests
        format_type="plain",
        silence_sql=True
    )


# Convenience function for getting component loggers
def get_component_logger(component: str) -> logging.Logger:
    """
    Get a logger for a specific component with consistent naming.

    Args:
        component: Component name (e.g., 'cli', 'web', 'mesh_manager')

    Returns:
        Logger instance
    """
    return get_logger(f"mesh_network.{component}")


# Example usage and testing
if __name__ == "__main__":
    # Test different logging configurations
    print("Testing logging configurations...")

    # Test CLI logging
    print("\n=== CLI Logging (plain format) ===")
    setup_cli_logging(verbose=1)
    logger = get_component_logger("test")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Test web logging
    print("\n=== Web Logging (JSON format) ===")
    setup_web_logging()
    logger = get_component_logger("web_test")
    logger.info("Web application started", extra={"port": 8000, "debug": False})
    logger.warning("High memory usage detected", extra={"memory_mb": 512})

    print("\nLogging configuration test complete.")