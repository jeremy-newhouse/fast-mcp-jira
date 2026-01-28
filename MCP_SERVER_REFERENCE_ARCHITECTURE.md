# MCP Server Reference Architecture

A production-ready reference architecture for building FastMCP servers with external API integrations.

## Table of Contents

1. [Introduction & Overview](#1-introduction--overview)
2. [Project Structure](#2-project-structure)
3. [Server Setup](#3-server-setup)
4. [Configuration Management](#4-configuration-management)
5. [Authentication](#5-authentication)
6. [Structured Logging](#6-structured-logging)
7. [Error Handling](#7-error-handling)
8. [HTTP Client Service](#8-http-client-service)
9. [Caching Service](#9-caching-service)
10. [Input Validation](#10-input-validation)
11. [Tool Implementation Patterns](#11-tool-implementation-patterns)
12. [Bulk Operations](#12-bulk-operations)
13. [Entry Point](#13-entry-point)
14. [Security Checklist](#14-security-checklist)
15. [Dependencies](#15-dependencies)

---

## 1. Introduction & Overview

This document provides a generic, domain-agnostic reference architecture for building production-ready MCP (Model Context Protocol) servers using FastMCP. The patterns are extracted from a real-world implementation and can be applied to any external API integration.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MCP Client (LLM)                              │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP/SSE (MCP Protocol)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastMCP Server                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   server.py │  │   auth.py   │  │  config.py  │  │  errors.py  │   │
│  │  (FastMCP)  │  │  (API Key)  │  │ (Settings)  │  │ (Hierarchy) │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        tools/                                     │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │entities.py││metadata.py││  bulk.py ││  cache.py │ ...        │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       services/                                   │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                      │   │
│  │  │  api_client.py   │  │     cache.py     │                      │   │
│  │  │ (HTTP + Rate Lim)│  │ (SQLite + TTL)   │                      │   │
│  │  └──────────────────┘  └──────────────────┘                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        utils/                                     │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                      │   │
│  │  │  validation.py   │  │   transforms.py  │                      │   │
│  │  │ (Input + XSS)    │  │ (Data Formats)   │                      │   │
│  │  └──────────────────┘  └──────────────────┘                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTPS (API Calls)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         External API                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Principles

1. **Defense in Depth**: Multiple validation layers (input, processing, output)
2. **Fail Secure**: Generic error messages to clients, detailed logging server-side
3. **Graceful Degradation**: Cache and non-critical features fail silently
4. **Observability**: Structured logging, timing metrics, correlation IDs
5. **Configuration over Code**: Environment-driven settings with secure defaults

---

## 2. Project Structure

### Recommended Directory Layout

```
src/your_mcp_server/
├── __init__.py              # Package initialization
├── __main__.py              # Entry point: logging setup, server start
├── server.py                # FastMCP instance, global services, tool imports
├── config.py                # Pydantic Settings with validation
├── auth.py                  # MCP endpoint authentication
├── errors.py                # Error hierarchy and formatters
├── logging_config.py        # Structured logging setup
├── services/
│   ├── __init__.py
│   ├── api_client.py        # HTTP client with rate limiting
│   └── cache.py             # SQLite cache service
├── tools/
│   ├── __init__.py
│   ├── entities.py          # Core CRUD tools
│   ├── metadata.py          # Cached metadata tools
│   ├── bulk.py              # Batch operation tools
│   └── cache.py             # Cache management tools
└── utils/
    ├── __init__.py
    ├── validation.py        # Input validators, XSS sanitization
    └── transforms.py        # Data format conversions
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `server.py` | Creates FastMCP instance, initializes global services, imports tools |
| `config.py` | Environment-based configuration with validation |
| `auth.py` | API key authentication with rate limiting |
| `errors.py` | Standardized error types and response formatting |
| `logging_config.py` | JSON/console logging with sensitive data redaction |
| `services/api_client.py` | HTTP client with rate limiting, retry, error handling |
| `services/cache.py` | SQLite cache with TTL, encryption, multi-tenant support |
| `utils/validation.py` | Input validation, XSS sanitization, response building |
| `tools/*.py` | MCP tool implementations (one file per domain) |

---

## 3. Server Setup

### Pattern: Global Instances with Lifespan Management

```python
"""FastMCP server instance and tool registration."""

import time
from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from .auth import ApiKeyVerifier
from .config import get_settings
from .logging_config import get_logger
from .services.cache import CacheService
from .services.api_client import ApiClient

logger = get_logger(__name__)

# Initialize settings and API client
settings = get_settings()
api = ApiClient(settings)

# Initialize cache service (if enabled)
cache: CacheService | None = None
if settings.cache_enabled:
    cache = CacheService(settings)

# Configure authentication if API key is set
auth_provider = None
if settings.mcp_api_key:
    auth_provider = ApiKeyVerifier(api_key=settings.mcp_api_key)
else:
    logger.warning(
        "MCP_API_KEY not set - endpoint is UNAUTHENTICATED. "
        "Set MCP_API_KEY environment variable for production deployments."
    )


@lifespan
async def app_lifespan(server: FastMCP) -> dict:
    """Initialize and cleanup server services."""
    logger.info("Starting MCP server services")

    # Startup: initialize cache
    if cache:
        await cache.initialize()
        logger.info(
            "Cache service initialized",
            extra={"cache_enabled": True, "cache_path": str(settings.cache_db_full_path)},
        )

    try:
        yield {"cache": cache, "api": api}
    finally:
        # Shutdown: cleanup services with timing
        logger.info("Shutdown initiated")
        start_time = time.time()

        # Close API client
        try:
            await api.close()
            logger.info(
                "API client closed",
                extra={"elapsed_ms": round((time.time() - start_time) * 1000, 2)},
            )
        except Exception as e:
            logger.error("API client close failed", extra={"error": str(e)})

        # Close cache service
        if cache:
            try:
                await cache.close()
                logger.info(
                    "Cache service closed",
                    extra={"elapsed_ms": round((time.time() - start_time) * 1000, 2)},
                )
            except Exception as e:
                logger.error("Cache service close failed", extra={"error": str(e)})

        logger.info(
            "Shutdown complete",
            extra={"total_ms": round((time.time() - start_time) * 1000, 2)},
        )


# Create FastMCP server
mcp = FastMCP(
    name="Your MCP Server",
    instructions="""
    Your server description and usage instructions here.
    """,
    auth=auth_provider,
    lifespan=app_lifespan,
)


# Import and register all tools (side-effect registration via decorators)
from .tools import (  # noqa: E402, F401
    entities,
    metadata,
    bulk,
)
from .tools import cache as cache_tools  # noqa: E402, F401
```

### Key Patterns

1. **Global Instances**: `settings`, `api`, `cache`, `mcp` are module-level for tool access
2. **Conditional Auth**: Warning logged when authentication is disabled
3. **Lifespan Management**: Startup initialization and graceful shutdown with timing
4. **Side-Effect Registration**: Tool imports at module bottom trigger decorator registration

---

## 4. Configuration Management

### Pattern: Pydantic Settings with Security Validation

```python
"""Configuration settings using pydantic-settings."""

import hashlib
import ipaddress
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_private_or_internal_ip(hostname: str) -> bool:
    """Check if hostname is a private, loopback, or link-local IP (SSRF prevention)."""
    if not hostname:
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False  # Not a valid IP - likely a hostname


def _is_allowed_hostname(hostname: str, allowed_patterns: list[str]) -> bool:
    """Check if hostname matches any allowed pattern (glob-style with *)."""
    import fnmatch

    if not hostname or not allowed_patterns:
        return False
    hostname_lower = hostname.lower()
    for pattern in allowed_patterns:
        if fnmatch.fnmatch(hostname_lower, pattern.lower()):
            return True
    return False


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required API configuration
    api_url: str
    api_email: str
    api_token: str

    # SSL configuration
    api_ssl_verify: bool = True

    # SSRF protection: allowed hostname patterns
    api_allowed_hosts: list[str] = ["*.example.com"]

    # Server configuration
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000

    # Logging
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    # HTTP client settings
    request_timeout: float = 30.0
    upload_timeout: float = 60.0
    rate_limit_per_second: float = 10.0
    rate_limit_burst: int = 20

    # MCP endpoint authentication (optional)
    mcp_api_key: str | None = None

    # Cache configuration
    cache_enabled: bool = True
    cache_db_path: str = "~/.your-mcp-server/cache.db"
    cache_ttl_metadata: int = 2592000  # 30 days
    cache_ttl_users: int = 604800      # 7 days (shorter for privacy)
    cache_cleanup_interval: int = 86400  # Daily
    cache_max_entries: int = 10000

    # Cache encryption (optional)
    cache_encryption_enabled: bool = False
    cache_encryption_key: str | None = None
    cache_encryption_key_file: str | None = None

    # Bulk operation limits
    bulk_max_batch_size: int = 100
    bulk_concurrent_requests: int = 10

    @property
    def cache_db_full_path(self) -> Path:
        """Get expanded cache database path."""
        path = Path(os.path.expanduser(self.cache_db_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def base_url(self) -> str:
        """Get the API base URL with SSRF prevention."""
        url = self.api_url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # SSRF Prevention: Block private/internal IPs
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if _is_private_or_internal_ip(hostname):
            raise ValueError(
                f"API URL points to private/internal IP: {hostname}. "
                "Blocked for security reasons (SSRF prevention)."
            )

        # SSRF Prevention: Validate hostname against allowlist
        if self.api_allowed_hosts and not _is_allowed_hostname(hostname, self.api_allowed_hosts):
            raise ValueError(
                f"API hostname '{hostname}' not in allowed hosts list. "
                f"Allowed: {self.api_allowed_hosts}"
            )

        return url.rstrip("/")

    @property
    def cache_partition_key(self) -> str:
        """Get cache partition key for multi-tenant isolation."""
        key_parts = [self.base_url]
        if self.mcp_api_key:
            key_parts.append(self.mcp_api_key)
        else:
            key_parts.append(self.api_email)
        combined = ":".join(key_parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    @property
    def cache_encryption_key_resolved(self) -> str | None:
        """Resolve encryption key from env var or file with permission validation."""
        if not self.cache_encryption_enabled:
            return None

        # Priority 1: Direct environment variable
        if self.cache_encryption_key:
            if len(self.cache_encryption_key) < 32:
                raise ValueError("Encryption key must be at least 32 characters")
            return self.cache_encryption_key

        # Priority 2: Key file with permission validation
        if self.cache_encryption_key_file:
            key_path = Path(os.path.expanduser(self.cache_encryption_key_file))
            if not key_path.exists():
                raise FileNotFoundError(f"Encryption key file not found: {key_path}")

            # Security: Verify restrictive permissions (owner read/write only)
            stat = key_path.stat()
            if stat.st_mode & 0o077:
                raise PermissionError(
                    f"Key file has insecure permissions: {oct(stat.st_mode)}. "
                    "Must be 0o600. Fix with: chmod 600 <file>"
                )

            key = key_path.read_text().strip()
            if len(key) < 32:
                raise ValueError("Encryption key from file must be at least 32 characters")
            return key

        raise ValueError("Encryption enabled but no key provided")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Key Patterns

1. **SSRF Prevention**: Private IP blocking + hostname allowlist
2. **Computed Properties**: Derived configuration with validation
3. **Partition Keys**: Multi-tenant cache isolation via SHA256 hash
4. **Key File Permissions**: Validates 0o600 for encryption key files
5. **Cached Accessor**: Single `get_settings()` call throughout application

---

## 5. Authentication

### Pattern: API Key with Rate-Limited Brute Force Protection

```python
"""API key authentication with rate limiting."""

import asyncio
import hmac
import logging
from time import monotonic

from fastmcp.server.auth import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)

# Rate limiting constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 60.0  # seconds
ATTEMPT_WINDOW = 300.0   # seconds


class AuthRateLimiter:
    """Rate limiter for failed authentication attempts."""

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        lockout_duration: float = LOCKOUT_DURATION,
        window: float = ATTEMPT_WINDOW,
    ):
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration
        self.window = window
        self._failed_attempts: list[float] = []
        self._lockout_until: float = 0
        self._lock = asyncio.Lock()

    async def check_rate_limit(self) -> bool:
        """Check if requests should be allowed. Returns False if rate limited."""
        async with self._lock:
            now = monotonic()
            if now < self._lockout_until:
                remaining = self._lockout_until - now
                logger.warning("Auth rate limited - lockout remaining: %.1fs", remaining)
                return False
            # Clean up old attempts outside window
            self._failed_attempts = [t for t in self._failed_attempts if now - t < self.window]
            return True

    async def record_failure(self) -> None:
        """Record failed auth attempt, trigger lockout if threshold exceeded."""
        async with self._lock:
            now = monotonic()
            self._failed_attempts.append(now)
            self._failed_attempts = [t for t in self._failed_attempts if now - t < self.window]

            if len(self._failed_attempts) >= self.max_attempts:
                self._lockout_until = now + self.lockout_duration
                logger.warning(
                    "Auth rate limit triggered - locked out for %.1fs",
                    self.lockout_duration,
                )

    async def record_success(self) -> None:
        """Record successful auth (clears failure count)."""
        async with self._lock:
            self._failed_attempts.clear()
            self._lockout_until = 0


class ApiKeyVerifier(TokenVerifier):
    """API key verifier with timing-safe comparison and rate limiting."""

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self._rate_limiter = AuthRateLimiter()

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify token with rate limiting and constant-time comparison."""
        # Check rate limit before verification
        if not await self._rate_limiter.check_rate_limit():
            return None

        # Constant-time comparison prevents timing attacks
        if not hmac.compare_digest(token, self.api_key):
            await self._rate_limiter.record_failure()
            return None

        await self._rate_limiter.record_success()
        return AccessToken(
            token=token,
            client_id="api-key-client",
            scopes=[],
            expires_at=None,
            claims={},
        )
```

### Key Patterns

1. **Timing-Safe Comparison**: `hmac.compare_digest()` prevents timing attacks
2. **Sliding Window Rate Limiting**: Tracks failures within a time window
3. **Lockout Mechanism**: Blocks auth attempts after threshold exceeded
4. **Async Lock**: Thread-safe state management

---

## 6. Structured Logging

### Pattern: Dual Formatters with Sensitive Data Redaction

```python
"""Structured logging with sensitive data redaction."""

import contextvars
import functools
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

# Correlation ID for request tracing
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

T = TypeVar("T")

# Sensitive fields to redact
SENSITIVE_LOG_FIELDS_EXACT = {
    "password", "secret", "token", "api_key", "apikey", "authorization",
    "credential", "encryption_key", "access_key", "secret_key", "private_key",
}
SENSITIVE_LOG_SUFFIXES = ("_password", "_secret", "_token", "_credential")


def _sanitize_log_value(key: str, value: Any) -> Any:
    """Redact sensitive fields before logging."""
    key_lower = key.lower()
    if key_lower in SENSITIVE_LOG_FIELDS_EXACT:
        return "[REDACTED]"
    if key_lower.endswith(SENSITIVE_LOG_SUFFIXES):
        return "[REDACTED]"
    return value


class StructuredFormatter(logging.Formatter):
    """JSON formatter for production (log aggregation systems)."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID
        if correlation_id := correlation_id_var.get():
            log_data["correlation_id"] = correlation_id

        # Add extra fields with sanitization
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs", "pathname",
            "process", "processName", "relativeCreated", "stack_info",
            "exc_info", "exc_text", "thread", "threadName", "taskName", "message",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = _sanitize_log_value(key, value)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Colored console formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = f"{timestamp} {color}[{record.levelname:8}]{self.RESET} {record.name}: "
        message += record.getMessage()

        if correlation_id := correlation_id_var.get():
            message += f" [cid={correlation_id}]"

        if record.exc_info:
            message += "\n" + self.formatException(record.exc_info)

        return message


def setup_logging(level: str = "INFO", json_format: bool = False, stream: Any = None) -> None:
    """Configure application-wide logging."""
    if stream is None:
        stream = sys.stderr  # stdout reserved for MCP protocol

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream)
    handler.setLevel(numeric_level)
    handler.setFormatter(StructuredFormatter() if json_format else ConsoleFormatter())
    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str | None) -> None:
    """Set correlation ID for request tracing."""
    correlation_id_var.set(correlation_id)


def timed(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to log function execution time."""
    logger = get_logger(func.__module__)

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "%s completed in %.2fms",
                func.__name__,
                elapsed_ms,
                extra={"timing_ms": elapsed_ms, "function": func.__name__},
            )
            return result
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "%s failed after %.2fms",
                func.__name__,
                elapsed_ms,
                extra={"timing_ms": elapsed_ms, "function": func.__name__},
            )
            raise

    return async_wrapper
```

### Key Patterns

1. **Dual Formatters**: Console (dev) vs JSON (production)
2. **Sensitive Redaction**: Exact matches + suffix patterns
3. **Correlation IDs**: Context variables for request tracing
4. **@timed Decorator**: Performance monitoring
5. **stderr for Logs**: stdout reserved for MCP protocol

---

## 7. Error Handling

### Pattern: Standardized Error Hierarchy

```python
"""Standardized error types and handling."""

from typing import Any
from .logging_config import get_logger

logger = get_logger(__name__)


class ToolError(Exception):
    """Base exception for all tool errors."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int | None = None,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result: dict[str, Any] = {"message": self.message, "code": self.code}
        if self.status_code is not None:
            result["status_code"] = self.status_code
        if self.field is not None:
            result["field"] = self.field
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(ToolError):
    """Input validation error (400)."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            field=field,
            details=details,
        )


class ApiError(ToolError):
    """External API error."""

    def __init__(self, message: str, status_code: int | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="API_ERROR",
            status_code=status_code,
            details=details,
        )


class CacheError(ToolError):
    """Cache operation error (non-fatal)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="CACHE_ERROR",
            status_code=None,
            details=details,
        )


class RateLimitError(ToolError):
    """Rate limit exceeded (429)."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            status_code=429,
            details=details,
        )


class AuthenticationError(ToolError):
    """Authentication failed (401)."""

    def __init__(self, message: str = "Authentication failed", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
        )


class PermissionError(ToolError):
    """Permission denied (403)."""

    def __init__(self, message: str = "Permission denied", details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="PERMISSION_ERROR",
            status_code=403,
            details=details,
        )


def format_error_response(error: Exception) -> dict[str, Any]:
    """Convert any exception to standardized error response."""
    if isinstance(error, ToolError):
        return {"success": False, "error": error.to_dict()}

    # Security: Log actual error but return generic message
    logger.exception("Unexpected error", extra={"error_type": type(error).__name__})
    return {
        "success": False,
        "error": {"message": "An unexpected error occurred", "code": "UNKNOWN_ERROR"},
    }


def format_success_response(data: Any, cached: bool = False, timing_ms: float | None = None) -> dict[str, Any]:
    """Create standardized success response."""
    response: dict[str, Any] = {"success": True, "data": data}
    if cached:
        response["_cached"] = True
    if timing_ms is not None:
        response["_timing_ms"] = round(timing_ms, 2)
    return response
```

### Key Patterns

1. **Error Hierarchy**: Base class with specialized subclasses
2. **Machine-Readable Codes**: `VALIDATION_ERROR`, `API_ERROR`, etc.
3. **to_dict() Serialization**: Clean JSON output
4. **Generic Error Responses**: Prevents information disclosure
5. **Server-Side Logging**: Full exception details logged internally

---

## 8. HTTP Client Service

### Pattern: Token Bucket Rate Limiting with Retry

```python
"""HTTP client with rate limiting and error handling."""

import asyncio
import base64
import logging
from time import monotonic
from typing import Any

import httpx
from .config import Settings

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 500
MAX_RESPONSE_SIZE = 50_000_000  # 50MB
MAX_429_RETRIES = 3
MAX_RETRY_AFTER_SECONDS = 120

SENSITIVE_PARAM_KEYS = {"body", "content", "password", "token", "secret", "key"}


def _sanitize_params_for_logging(params: dict | None) -> str:
    """Redact sensitive parameters before logging."""
    if not params:
        return "{}"
    sanitized = {}
    for key, value in params.items():
        if key.lower() in SENSITIVE_PARAM_KEYS:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 100:
            sanitized[key] = f"{value[:50]}...[truncated]"
        else:
            sanitized[key] = value
    return str(sanitized)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_second: float = 10.0, burst: int = 20):
        self.rate = requests_per_second
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a rate limit token, waiting if necessary."""
        async with self._lock:
            now = monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self.rate
                logger.debug("Rate limit: waiting %.2fs", wait_time)
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


class ApiError(Exception):
    """Exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class ApiClient:
    """Async HTTP client with rate limiting and error handling."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(
            requests_per_second=settings.rate_limit_per_second,
            burst=settings.rate_limit_burst,
        )

    def _get_auth_header(self) -> str:
        """Generate Basic auth header."""
        credentials = f"{self.settings.api_email}:{self.settings.api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (lazy initialization)."""
        if self._client is None:
            if not self.settings.api_ssl_verify:
                logger.warning(
                    "SSL verification DISABLED - vulnerable to MITM attacks. "
                    "Only disable for development with self-signed certificates."
                )

            self._client = httpx.AsyncClient(
                base_url=self.settings.base_url,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                verify=self.settings.api_ssl_verify,
                timeout=self.settings.request_timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _sanitize_error_message(self, message: str) -> str:
        """Truncate error message to prevent info leakage."""
        if len(message) > MAX_ERROR_MESSAGE_LENGTH:
            message = message[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."
        return message

    def _validate_response_size(self, response: httpx.Response) -> None:
        """Validate response size to prevent DoS."""
        if len(response.content) > MAX_RESPONSE_SIZE:
            raise ApiError(
                f"Response too large: {len(response.content)} bytes (max: {MAX_RESPONSE_SIZE})",
                status_code=response.status_code,
            )

    def _handle_error(self, response: httpx.Response) -> None:
        """Extract and sanitize error from response."""
        try:
            error_data = response.json()
            message = error_data.get("message") or error_data.get("error") or "Request failed"
        except Exception:
            message = "Request failed"

        message = self._sanitize_error_message(message)
        raise ApiError(
            f"API error ({response.status_code}): {message}",
            status_code=response.status_code,
        )

    async def _handle_rate_limit(self, response: httpx.Response, attempt: int) -> bool:
        """Handle 429 with Retry-After. Returns True if should retry."""
        if response.status_code != 429:
            return False

        if attempt >= MAX_429_RETRIES - 1:
            logger.error("Max retries exceeded for rate limit (429)")
            return False

        retry_after = response.headers.get("Retry-After", "60")
        try:
            wait_seconds = min(int(retry_after), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            wait_seconds = 60

        logger.warning(
            "Rate limited (429). Retrying in %d seconds (attempt %d/%d)",
            wait_seconds, attempt + 1, MAX_429_RETRIES,
        )
        await asyncio.sleep(wait_seconds)
        return True

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        """GET request with rate limiting and 429 retry."""
        for attempt in range(MAX_429_RETRIES):
            await self._rate_limiter.acquire()
            logger.debug("GET %s params=%s", path, _sanitize_params_for_logging(params))
            response = await self.client.get(path, params=params)

            if await self._handle_rate_limit(response, attempt):
                continue

            if not response.is_success:
                self._handle_error(response)

            self._validate_response_size(response)
            return response.json() if response.content else {}

        self._handle_error(response)
        return {}

    async def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """POST request with rate limiting."""
        for attempt in range(MAX_429_RETRIES):
            await self._rate_limiter.acquire()
            logger.debug("POST %s", path)
            response = await self.client.post(path, json=body)

            if await self._handle_rate_limit(response, attempt):
                continue

            if not response.is_success:
                self._handle_error(response)

            self._validate_response_size(response)
            return response.json() if response.content else {}

        self._handle_error(response)
        return {}

    async def put(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """PUT request with rate limiting."""
        for attempt in range(MAX_429_RETRIES):
            await self._rate_limiter.acquire()
            logger.debug("PUT %s", path)
            response = await self.client.put(path, json=body)

            if await self._handle_rate_limit(response, attempt):
                continue

            if not response.is_success:
                self._handle_error(response)

            self._validate_response_size(response)
            return response.json() if response.content else {}

        self._handle_error(response)
        return {}

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """DELETE request with rate limiting."""
        for attempt in range(MAX_429_RETRIES):
            await self._rate_limiter.acquire()
            logger.debug("DELETE %s", path)
            response = await self.client.delete(path, params=params)

            if await self._handle_rate_limit(response, attempt):
                continue

            if not response.is_success:
                self._handle_error(response)

            self._validate_response_size(response)
            return response.json() if response.content else {}

        self._handle_error(response)
        return {}

    async def post_multipart(
        self, path: str, filename: str, content: bytes, content_type: str = "application/octet-stream"
    ) -> dict[str, Any]:
        """Multipart POST for file uploads."""
        files = {"file": (filename, content, content_type)}
        headers = {
            "Authorization": self._get_auth_header(),
            "Accept": "application/json",
        }

        for attempt in range(MAX_429_RETRIES):
            await self._rate_limiter.acquire()
            logger.debug("POST multipart %s filename=%s size=%d", path, filename, len(content))

            async with httpx.AsyncClient(
                base_url=self.settings.base_url,
                verify=self.settings.api_ssl_verify,
                timeout=self.settings.upload_timeout,
            ) as client:
                response = await client.post(path, files=files, headers=headers)

            if await self._handle_rate_limit(response, attempt):
                continue

            if not response.is_success:
                self._handle_error(response)

            self._validate_response_size(response)
            return response.json() if response.content else {}

        self._handle_error(response)
        return {}
```

### Key Patterns

1. **Token Bucket**: Smooth rate limiting with burst capacity
2. **429 Retry**: Respects Retry-After header with cap
3. **Response Size Limits**: 50MB max to prevent DoS
4. **Error Sanitization**: Truncates messages to 500 chars
5. **SSL Warnings**: Logged when verification disabled
6. **Lazy Client Init**: Created on first use

---

## 9. Caching Service

### Pattern: SQLite Cache with TTL and Multi-Tenant Support

```python
"""SQLite-based async cache service."""

import asyncio
import hashlib
import json
import time
from enum import Enum
from pathlib import Path
from typing import Any

import aiosqlite
from .config import Settings
from .logging_config import get_logger

logger = get_logger(__name__)


class CacheCategory(str, Enum):
    """Cache categories with different TTLs."""
    METADATA = "metadata"  # Long-lived reference data
    PROJECTS = "projects"  # Project-related data
    USERS = "users"        # Shorter TTL for privacy


ENTITY_CATEGORY_MAP: dict[str, CacheCategory] = {
    "entity_types": CacheCategory.METADATA,
    "priorities": CacheCategory.METADATA,
    "statuses": CacheCategory.METADATA,
    "projects": CacheCategory.PROJECTS,
    "users": CacheCategory.USERS,
}

# Sensitive fields to filter before caching
SENSITIVE_FIELDS_BY_ENTITY: dict[str, set[str]] = {
    "users": {"emailAddress", "email", "avatarUrls"},
}
SENSITIVE_FIELDS_GLOBAL: set[str] = {
    "password", "token", "secret", "credential", "apiToken", "accessToken",
}


def _filter_sensitive_data(data: Any, entity_type: str) -> Any:
    """Remove sensitive fields before caching."""
    if isinstance(data, dict):
        entity_sensitive = SENSITIVE_FIELDS_BY_ENTITY.get(entity_type, set())
        filtered = {}
        for key, value in data.items():
            if key in SENSITIVE_FIELDS_GLOBAL or key in entity_sensitive:
                continue
            filtered[key] = _filter_sensitive_data(value, entity_type)
        return filtered
    if isinstance(data, list):
        return [_filter_sensitive_data(item, entity_type) for item in data]
    return data


class CacheService:
    """Async SQLite cache with TTL and multi-tenant support."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._db: aiosqlite.Connection | None = None
        self._db_path: Path = settings.cache_db_full_path
        self._lock = asyncio.Lock()
        self._initialized = False
        self._cleanup_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """Initialize database and start cleanup task."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            self._db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._db = await aiosqlite.connect(str(self._db_path))
            self._db.row_factory = aiosqlite.Row

            # Optional SQLCipher encryption
            if self.settings.cache_encryption_enabled:
                try:
                    key = self.settings.cache_encryption_key_resolved
                    if key:
                        hex_key = key.encode("utf-8").hex()
                        await self._db.execute(f"PRAGMA key = \"x'{hex_key}'\"")
                        await self._db.execute("PRAGMA cipher_compatibility = 4")
                        logger.info("Cache encryption enabled")
                except Exception as e:
                    logger.warning("Cache encryption failed", extra={"error": str(e)})
            else:
                logger.warning("Cache encryption DISABLED - data stored unencrypted")

            await self._db.execute("PRAGMA journal_mode=WAL")
            await self._create_schema()
            self._initialized = True
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _create_schema(self) -> None:
        """Create database tables."""
        if self._db is None:
            return
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                partition_key TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);
            CREATE INDEX IF NOT EXISTS idx_cache_partition ON cache(partition_key);

            CREATE TABLE IF NOT EXISTS cache_stats (
                entity_type TEXT PRIMARY KEY,
                hit_count INTEGER DEFAULT 0,
                miss_count INTEGER DEFAULT 0
            );
        """)
        await self._db.commit()

    def _get_ttl(self, entity_type: str) -> int:
        """Get TTL for entity type."""
        category = ENTITY_CATEGORY_MAP.get(entity_type, CacheCategory.METADATA)
        return {
            CacheCategory.METADATA: self.settings.cache_ttl_metadata,
            CacheCategory.PROJECTS: self.settings.cache_ttl_metadata,
            CacheCategory.USERS: self.settings.cache_ttl_users,
        }.get(category, self.settings.cache_ttl_metadata)

    @staticmethod
    def make_key(entity_type: str, *parts: str | int) -> str:
        """Create cache key from entity type and parts."""
        if parts:
            return f"{entity_type}:{':'.join(str(p) for p in parts)}"
        return f"{entity_type}:all"

    @staticmethod
    def hash_params(params: dict[str, Any] | None) -> str:
        """Create hash of query parameters for cache key."""
        if not params:
            return "default"
        serialized = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:12]

    async def get(self, cache_key: str, entity_type: str) -> dict[str, Any] | list[Any] | None:
        """Get cached value if not expired."""
        if not self._initialized or self._db is None:
            return None

        try:
            cursor = await self._db.execute(
                """SELECT value FROM cache
                   WHERE cache_key = ? AND partition_key = ? AND expires_at > ?""",
                (cache_key, self.settings.cache_partition_key, time.time()),
            )
            row = await cursor.fetchone()

            if row:
                await self._record_hit(entity_type)
                return json.loads(row["value"])
            else:
                await self._record_miss(entity_type)
                return None
        except Exception as e:
            logger.warning("Cache get error", extra={"cache_key": cache_key, "error": str(e)})
            return None

    async def set(self, cache_key: str, entity_type: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache with TTL."""
        if not self._initialized or self._db is None:
            return

        try:
            actual_ttl = ttl if ttl is not None else self._get_ttl(entity_type)
            filtered_value = _filter_sensitive_data(value, entity_type)

            await self._db.execute(
                """INSERT OR REPLACE INTO cache
                   (cache_key, entity_type, value, created_at, expires_at, partition_key)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    cache_key,
                    entity_type,
                    json.dumps(filtered_value),
                    time.time(),
                    time.time() + actual_ttl,
                    self.settings.cache_partition_key,
                ),
            )
            await self._db.commit()
        except Exception as e:
            logger.warning("Cache set error", extra={"cache_key": cache_key, "error": str(e)})

    async def invalidate(self, cache_key: str | None = None, entity_type: str | None = None) -> int:
        """Invalidate cache entries. Returns count removed."""
        if not self._initialized or self._db is None:
            return 0

        try:
            if cache_key:
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE cache_key = ? AND partition_key = ?",
                    (cache_key, self.settings.cache_partition_key),
                )
            elif entity_type:
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE entity_type = ? AND partition_key = ?",
                    (entity_type, self.settings.cache_partition_key),
                )
            else:
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE partition_key = ?",
                    (self.settings.cache_partition_key,),
                )
            await self._db.commit()
            return cursor.rowcount
        except Exception as e:
            logger.warning("Cache invalidate error", extra={"error": str(e)})
            return 0

    async def _record_hit(self, entity_type: str) -> None:
        """Record cache hit (non-critical)."""
        if self._db is None:
            return
        try:
            await self._db.execute(
                """INSERT INTO cache_stats (entity_type, hit_count) VALUES (?, 1)
                   ON CONFLICT(entity_type) DO UPDATE SET hit_count = hit_count + 1""",
                (entity_type,),
            )
            await self._db.commit()
        except Exception:
            pass

    async def _record_miss(self, entity_type: str) -> None:
        """Record cache miss (non-critical)."""
        if self._db is None:
            return
        try:
            await self._db.execute(
                """INSERT INTO cache_stats (entity_type, miss_count) VALUES (?, 1)
                   ON CONFLICT(entity_type) DO UPDATE SET miss_count = miss_count + 1""",
                (entity_type,),
            )
            await self._db.commit()
        except Exception:
            pass

    async def _periodic_cleanup(self) -> None:
        """Background task for expired entry cleanup."""
        while True:
            try:
                await asyncio.sleep(self.settings.cache_cleanup_interval)
                if self._db:
                    await self._db.execute(
                        "DELETE FROM cache WHERE expires_at < ? AND partition_key = ?",
                        (time.time(), self.settings.cache_partition_key),
                    )
                    await self._db.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Cache cleanup error", extra={"error": str(e)})

    async def close(self) -> None:
        """Close database with graceful task cancellation."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        if self._db:
            try:
                await asyncio.wait_for(self._db.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Database close exceeded timeout")
            self._db = None
            self._initialized = False
```

### Key Patterns

1. **TTL Categories**: Different expiration for metadata vs users
2. **Sensitive Filtering**: PII removed before storage
3. **Partition Keys**: Multi-tenant isolation via SHA256 hash
4. **Optional Encryption**: SQLCipher support for at-rest encryption
5. **Background Cleanup**: Periodic expired entry removal
6. **Graceful Shutdown**: Timeout-based task cancellation

---

## 10. Input Validation

### Pattern: Pydantic Models with XSS Sanitization

```python
"""Input validation with XSS prevention."""

import re
from typing import Any

import bleach
from pydantic import BaseModel, ConfigDict, Field, field_validator

# XSS sanitization configuration
ALLOWED_HTML_TAGS = [
    "p", "br", "b", "i", "u", "strong", "em", "a", "ul", "ol", "li",
    "code", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
]
ALLOWED_HTML_ATTRIBUTES = {
    "a": ["href", "title"],
    "code": ["class"],
    "pre": ["class"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


class EntityKeyInput(BaseModel):
    """Validated entity key (e.g., PROJECT-123)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    entity_key: str = Field(..., description="Entity key (e.g., PROJ-123)")

    @field_validator("entity_key")
    @classmethod
    def validate_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z][A-Z0-9_]+-\d+$", v):
            raise ValueError(f"Invalid key format '{v}'. Expected: PROJECT-123")
        return v


class ResourceKeyInput(BaseModel):
    """Validated resource key (e.g., PROJ)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    resource_key: str = Field(..., max_length=10)

    @field_validator("resource_key")
    @classmethod
    def validate_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r"^[A-Z][A-Z0-9_]*$", v):
            raise ValueError("Must start with letter, contain only letters/numbers/underscores")
        return v


class AttachmentInput(BaseModel):
    """Validated attachment with path traversal prevention."""

    model_config = ConfigDict(str_strip_whitespace=True)

    filename: str = Field(..., max_length=255)
    content_base64: str = Field(..., max_length=70_000_000)  # ~50MB
    content_type: str = Field(default="application/octet-stream")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        v = v.strip()
        # Path traversal prevention
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename contains invalid path characters")
        if "\x00" in v:
            raise ValueError("Filename contains null byte")
        if v.startswith("."):
            raise ValueError("Hidden files not allowed")
        # Dangerous extensions
        dangerous = {".exe", ".bat", ".cmd", ".sh", ".ps1", ".dll", ".so"}
        ext = ("." + v.rsplit(".", 1)[-1].lower()) if "." in v else ""
        if ext in dangerous:
            raise ValueError(f"File type {ext} not allowed")
        return v


class QueryInput(BaseModel):
    """Validated query with injection prevention."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(..., max_length=10000)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        v = v.strip()
        # SQL-like injection patterns
        dangerous = [r";", r"--", r"/\*", r"\*/"]
        for pattern in dangerous:
            if re.search(pattern, v.lower()):
                raise ValueError("Query contains potentially dangerous characters")
        return v


class LabelListInput(BaseModel):
    """Validated label list."""

    labels: list[str] = Field(default_factory=list)

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: list[str]) -> list[str]:
        validated = []
        for label in v:
            label = label.strip()
            if not label:
                continue
            if len(label) > 255:
                raise ValueError("Label exceeds 255 characters")
            if not re.match(r"^[a-zA-Z0-9_-]+$", label):
                raise ValueError(f"Label '{label}' contains invalid characters")
            validated.append(label)
        return validated


# Allowed fields for bulk updates (security whitelist)
ALLOWED_BULK_UPDATE_FIELDS = {
    "summary", "description", "priority", "labels", "assignee",
}


class BulkUpdateFieldsInput(BaseModel):
    """Validated bulk update fields with whitelist."""

    updates: dict[str, Any] = Field(...)

    @field_validator("updates")
    @classmethod
    def validate_fields(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("No updates provided")
        for field_name in v.keys():
            if field_name in ALLOWED_BULK_UPDATE_FIELDS:
                continue
            if field_name.startswith("customfield_"):
                if not re.match(r"^customfield_\d+$", field_name):
                    raise ValueError(f"Invalid custom field: '{field_name}'")
                continue
            raise ValueError(f"Field '{field_name}' not allowed in bulk updates")
        return v


class ValidationError(Exception):
    """Validation error with field information."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_entity_key(entity_key: str) -> str:
    """Validate entity key format."""
    try:
        return EntityKeyInput(entity_key=entity_key).entity_key
    except ValueError as e:
        raise ValidationError("entity_key", str(e))


def sanitize_for_response(data: Any) -> Any:
    """Sanitize data for XSS prevention using bleach allowlist."""
    if isinstance(data, str):
        return bleach.clean(
            data,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
        )
    if isinstance(data, dict):
        return {k: sanitize_for_response(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_for_response(item) for item in data]
    return data


def build_response(success: bool, **data: Any) -> dict[str, Any]:
    """Build sanitized tool response."""
    sanitized = {k: sanitize_for_response(v) for k, v in data.items()}
    return {"success": success, **sanitized}
```

### Key Patterns

1. **Pydantic Models**: Type-safe validation with field_validator
2. **Path Traversal Prevention**: Blocks `..`, `/`, `\`, null bytes
3. **Dangerous Extensions**: Whitelist approach for file types
4. **Injection Prevention**: Regex patterns for SQL-like attacks
5. **Field Whitelisting**: Bulk updates limited to safe fields
6. **XSS Sanitization**: Bleach with allowlist for HTML tags
7. **build_response()**: All output goes through sanitization

---

## 11. Tool Implementation Patterns

### Pattern: Basic Tool with Validation and Error Handling

```python
"""Tool implementation patterns."""

from typing import Annotated, Any
from pydantic import Field

from .server import api, mcp
from .services.api_client import ApiError
from .utils.validation import (
    ValidationError,
    build_response,
    validate_entity_key,
    validate_resource_key,
)
from .logging_config import get_logger

logger = get_logger(__name__)


@mcp.tool(description="Get details of an entity by its key.")
async def get_entity(
    entity_key: Annotated[str, Field(description="Entity key (e.g., PROJ-123)")],
    fields: Annotated[str | None, Field(description="Comma-separated fields to return")] = None,
) -> dict[str, Any]:
    """Get entity details."""
    try:
        # 1. VALIDATE INPUTS
        entity_key = validate_entity_key(entity_key)

        # 2. BUILD REQUEST
        params = {"fields": fields} if fields else None

        # 3. CALL API
        result = await api.get(f"/api/entity/{entity_key}", params=params)

        # 4. RETURN SANITIZED RESPONSE
        return build_response(True, entity=result)

    # 5. LAYERED ERROR HANDLING
    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except ApiError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting entity %s", entity_key)
        return build_response(False, error="Internal error occurred")


@mcp.tool(description="Create a new entity.")
async def create_entity(
    resource_key: Annotated[str, Field(description="Resource key (e.g., PROJ)")],
    summary: Annotated[str, Field(description="Entity summary (max 255 chars)")],
    description: Annotated[str | None, Field(description="Entity description")] = None,
    priority: Annotated[str | None, Field(description="Priority name")] = None,
) -> dict[str, Any]:
    """Create a new entity."""
    try:
        resource_key = validate_resource_key(resource_key)

        if not summary.strip():
            raise ValidationError("summary", "Summary is required")
        if len(summary) > 255:
            raise ValidationError("summary", "Summary exceeds 255 characters")

        fields: dict[str, Any] = {
            "resource": {"key": resource_key},
            "summary": summary.strip(),
        }

        if description:
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}

        result = await api.post("/api/entity", body={"fields": fields})

        return build_response(
            True,
            entity_key=result.get("key"),
            entity_id=result.get("id"),
        )

    except ValidationError as e:
        return build_response(False, error=str(e), field=e.field)
    except ApiError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error creating entity")
        return build_response(False, error="Internal error occurred")
```

### Pattern: Cached Tool

```python
from .server import api, cache, mcp
from .services.cache import CacheService


@mcp.tool(description="Get all entity types (cached).")
async def get_entity_types() -> dict[str, Any]:
    """Get list of entity types."""
    cache_key = CacheService.make_key("entity_types")

    # Check cache first
    if cache:
        cached = await cache.get(cache_key, "entity_types")
        if cached:
            cached["_cached"] = True
            return cached

    try:
        result = await api.get("/api/entity-types")

        response = build_response(
            True,
            total=len(result),
            entity_types=result,
        )

        # Store in cache
        if cache:
            await cache.set(cache_key, "entity_types", response)

        return response

    except ApiError as e:
        return build_response(False, error=str(e), status_code=e.status_code)
    except Exception:
        logger.exception("Unexpected error getting entity types")
        return build_response(False, error="Internal error occurred")
```

### Key Patterns

1. **Three-Phase Flow**: Validate → Execute → Respond
2. **Annotated Parameters**: Type hints + Field descriptions
3. **Layered Exceptions**: Specific → Generic catch-all
4. **Generic Error Message**: "Internal error occurred" hides details
5. **Cache-First Pattern**: Check cache before API call
6. **_cached Flag**: Indicates response source

---

## 12. Bulk Operations

### Pattern: Parallel Execution with Concurrency Control

```python
"""Bulk operation patterns."""

import asyncio
from typing import Annotated, Any

from pydantic import Field

from .config import get_settings
from .logging_config import get_logger
from .server import api, mcp
from .services.api_client import ApiError
from .utils.validation import (
    BulkUpdateFieldsInput,
    ValidationError,
    build_response,
    validate_entity_key,
)

logger = get_logger(__name__)


async def _update_single_entity(entity_key: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update a single entity and return result."""
    try:
        await api.put(f"/api/entity/{entity_key}", body={"fields": updates})
        return {"entity_key": entity_key, "success": True}
    except ApiError as e:
        return {"entity_key": entity_key, "success": False, "error": str(e)}
    except Exception:
        logger.exception("Error updating entity %s", entity_key)
        return {"entity_key": entity_key, "success": False, "error": "Internal error"}


@mcp.tool(description="Update multiple entities at once.")
async def bulk_update_entities(
    entity_keys: Annotated[list[str], Field(description="List of entity keys")],
    updates: Annotated[dict[str, Any], Field(description="Fields to update")],
) -> dict[str, Any]:
    """Update multiple entities with the same field values."""
    settings = get_settings()

    # Validate batch size
    if len(entity_keys) > settings.bulk_max_batch_size:
        return build_response(
            False,
            error=f"Batch size {len(entity_keys)} exceeds max {settings.bulk_max_batch_size}",
        )

    # Validate entity keys
    try:
        validated_keys = [validate_entity_key(key) for key in entity_keys]
    except ValidationError as e:
        return build_response(False, error=str(e), field="entity_keys")

    # Validate update fields (security whitelist)
    try:
        BulkUpdateFieldsInput(updates=updates)
    except ValueError as e:
        return build_response(False, error=str(e), field="updates")

    logger.info(
        "Starting bulk update",
        extra={"count": len(validated_keys), "fields": list(updates.keys())},
    )

    # Execute in parallel
    tasks = [_update_single_entity(key, updates) for key in validated_keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    processed = []
    success_count = 0
    failure_count = 0

    for result in results:
        if isinstance(result, Exception):
            processed.append({"success": False, "error": str(result)})
            failure_count += 1
        elif isinstance(result, dict):
            processed.append(result)
            if result.get("success"):
                success_count += 1
            else:
                failure_count += 1

    logger.info(
        "Bulk update completed",
        extra={"success": success_count, "failed": failure_count},
    )

    return build_response(
        failure_count == 0,
        total=len(validated_keys),
        updated=success_count,
        failed=failure_count,
        results=processed,
    )
```

### Key Patterns

1. **Batch Size Limits**: Configuration-driven maximum
2. **asyncio.gather()**: Parallel execution for performance
3. **Per-Item Results**: Track success/failure individually
4. **Field Whitelist**: Security via BulkUpdateFieldsInput
5. **Summary Response**: Total, success, failure counts
6. **Exception Handling**: Graceful handling of individual failures

---

## 13. Entry Point

### Pattern: Logging Setup Before Server Import

```python
"""Entry point for the MCP server."""

from .config import get_settings
from .logging_config import get_logger, setup_logging


def main() -> None:
    """Run the MCP server."""
    settings = get_settings()

    # Setup logging BEFORE importing server (captures all init logs)
    setup_logging(
        level=settings.log_level,
        json_format=settings.log_format.lower() == "json",
    )

    logger = get_logger(__name__)

    # Lazy import server after logging is configured
    from .server import mcp

    logger.info("Starting MCP server")
    logger.info(
        "Server configuration",
        extra={
            "api_url": settings.base_url,
            "ssl_verify": settings.api_ssl_verify,
            "host": settings.mcp_host,
            "port": settings.mcp_port,
            "cache_enabled": settings.cache_enabled,
            "auth_enabled": settings.mcp_api_key is not None,
        },
    )

    # Run with HTTP transport
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
```

### Key Patterns

1. **Logging First**: Setup before any imports that might log
2. **Lazy Server Import**: After logging configured
3. **Configuration Logging**: Non-sensitive settings only
4. **HTTP Transport**: Streamable HTTP for MCP protocol

---

## 14. Security Checklist

### Input Validation

- [ ] All user inputs validated before use
- [ ] Entity keys validated against regex pattern
- [ ] Query strings checked for injection patterns
- [ ] Filenames blocked for path traversal (`..`, `/`, `\`)
- [ ] Dangerous file extensions blocked (`.exe`, `.sh`, etc.)
- [ ] Input length limits enforced
- [ ] Bulk operation fields restricted to whitelist

### Output Sanitization

- [ ] All responses pass through `build_response()`
- [ ] HTML sanitized via bleach allowlist
- [ ] Only safe tags/attributes/protocols allowed
- [ ] Error messages truncated to prevent info leakage
- [ ] Generic error messages for unexpected exceptions

### Network Security

- [ ] SSRF prevention via private IP blocking
- [ ] Hostname allowlist for API URLs
- [ ] SSL verification enabled by default
- [ ] Warning logged when SSL disabled
- [ ] Response size limits (50MB default)

### Authentication

- [ ] Timing-safe comparison for API keys
- [ ] Rate limiting on failed auth attempts
- [ ] Lockout after threshold exceeded
- [ ] Warning when auth disabled

### Rate Limiting

- [ ] Token bucket for API requests
- [ ] 429 retry with Retry-After header
- [ ] Maximum retry attempts capped
- [ ] Maximum wait time capped

### Logging

- [ ] Sensitive fields redacted (password, token, etc.)
- [ ] Error details logged server-side only
- [ ] Correlation IDs for request tracing
- [ ] stderr used (stdout for MCP protocol)

### Caching

- [ ] Sensitive fields filtered before storage
- [ ] Encryption option available (SQLCipher)
- [ ] Key file permissions validated (0o600)
- [ ] Multi-tenant isolation via partition keys

### Configuration

- [ ] Secrets via environment variables
- [ ] Secure defaults for all settings
- [ ] Warnings for insecure configurations

---

## 15. Dependencies

### pyproject.toml Template

```toml
[project]
name = "your-mcp-server"
version = "0.1.0"
description = "MCP server for Your API"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=3.0.0b1,<4.0.0",
    "httpx>=0.28.0,<1.0.0",
    "pydantic>=2.0,<3.0",
    "pydantic-settings>=2.0,<3.0",
    "aiosqlite>=0.19.0,<1.0.0",
    "bleach>=6.0.0,<7.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
]
encryption = [
    "sqlcipher3-binary>=0.5.0,<1.0.0",
]

[project.scripts]
your-mcp-server = "your_mcp_server.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/your_mcp_server"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Core Dependencies

| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP server framework |
| `httpx` | Async HTTP client |
| `pydantic` | Data validation and serialization |
| `pydantic-settings` | Environment-based configuration |
| `aiosqlite` | Async SQLite access |
| `bleach` | HTML sanitization (XSS prevention) |

### Optional Dependencies

| Package | Purpose |
|---------|---------|
| `sqlcipher3-binary` | SQLite encryption at rest |

---

## License

This reference architecture is derived from the fast-mcp-jira project and is provided as a template for building production-ready MCP servers.
