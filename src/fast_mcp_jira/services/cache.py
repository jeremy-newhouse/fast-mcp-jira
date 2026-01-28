"""SQLite-based async cache service for JIRA API responses.

This module provides persistent caching with TTL-based expiration
for JIRA metadata and entity data. The cache survives server restarts
and supports multiple JIRA instances.

Features:
- Async SQLite access via aiosqlite
- TTL-based expiration with configurable durations per entity type
- Automatic background cleanup of expired entries
- Cache statistics tracking (hit/miss rates)
- Multi-JIRA-instance support (cache is partitioned by JIRA URL)

Usage:
    from .cache import CacheService

    cache = CacheService(settings)
    await cache.initialize()

    # Get or set cached data
    cached = await cache.get("issue_types:all", "issue_types")
    if cached is None:
        data = await fetch_from_jira()
        await cache.set("issue_types:all", "issue_types", data)

    await cache.close()
"""

import asyncio
import hashlib
import json
import time
from enum import Enum
from pathlib import Path
from typing import Any

import aiosqlite

from ..config import Settings
from ..logging_config import get_logger

logger = get_logger(__name__)


class CacheCategory(str, Enum):
    """Cache categories with associated TTL settings.

    Each category maps to a TTL setting in the configuration.
    """

    METADATA = "metadata"  # issue_types, priorities, statuses, fields, link_types
    PROJECTS = "projects"  # projects, components, versions
    AGILE = "agile"  # boards, sprints
    USERS = "users"  # user search results


# Mapping of entity types to cache categories
ENTITY_CATEGORY_MAP: dict[str, CacheCategory] = {
    "issue_types": CacheCategory.METADATA,
    "priorities": CacheCategory.METADATA,
    "statuses": CacheCategory.METADATA,
    "fields": CacheCategory.METADATA,
    "link_types": CacheCategory.METADATA,
    "projects": CacheCategory.PROJECTS,
    "project": CacheCategory.PROJECTS,
    "components": CacheCategory.PROJECTS,
    "versions": CacheCategory.PROJECTS,
    "boards": CacheCategory.AGILE,
    "board": CacheCategory.AGILE,
    "sprints": CacheCategory.AGILE,
    "users": CacheCategory.USERS,
}


class CacheService:
    """Async SQLite cache service for JIRA API responses.

    Provides persistent caching with TTL-based expiration. The cache
    is partitioned by JIRA instance URL to support multi-tenant setups.

    Attributes:
        settings: Application settings with cache configuration.

    Example:
        cache = CacheService(settings)
        await cache.initialize()

        # Check cache
        data = await cache.get("issue_types:all", "issue_types")

        # Store in cache
        await cache.set("issue_types:all", "issue_types", {"types": [...]})

        # Invalidate
        await cache.invalidate(entity_type="issue_types")

        await cache.close()
    """

    def __init__(self, settings: Settings):
        """Initialize cache service.

        Args:
            settings: Application settings with cache configuration.
        """
        self.settings = settings
        self._db: aiosqlite.Connection | None = None
        self._db_path: Path = settings.cache_db_full_path
        self._lock = asyncio.Lock()
        self._initialized = False
        self._cleanup_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """Initialize database connection and schema.

        Creates the SQLite database file and tables if they don't exist.
        Also starts the background cleanup task.

        This method is idempotent and safe to call multiple times.
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Ensure directory exists with restrictive permissions (owner only)
            self._db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

            self._db = await aiosqlite.connect(str(self._db_path))
            self._db.row_factory = aiosqlite.Row

            # Enable encryption if configured (requires SQLCipher-enabled SQLite)
            if self.settings.cache_encryption_enabled:
                try:
                    encryption_key = self.settings.cache_encryption_key_resolved
                    if encryption_key:
                        # Set encryption key via PRAGMA (SQLCipher)
                        # Note: This only works if SQLite is compiled with SQLCipher
                        await self._db.execute(f"PRAGMA key = '{encryption_key}'")
                        await self._db.execute("PRAGMA cipher_compatibility = 4")
                        logger.info("Cache encryption enabled (SQLCipher)")
                except Exception as e:
                    logger.warning(
                        "Cache encryption failed - ensure SQLCipher is available",
                        extra={"error": str(e)},
                    )

            # Enable WAL mode for better concurrent read performance
            await self._db.execute("PRAGMA journal_mode=WAL")

            # Create schema
            await self._create_schema()

            self._initialized = True
            logger.info(
                "Cache initialized",
                extra={"cache_path": str(self._db_path)},
            )

            # Start background cleanup task
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _create_schema(self) -> None:
        """Create database schema if not exists."""
        if self._db is None:
            return

        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                jira_instance TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON cache(expires_at);
            CREATE INDEX IF NOT EXISTS idx_cache_entity_type
                ON cache(entity_type);
            CREATE INDEX IF NOT EXISTS idx_cache_instance
                ON cache(jira_instance);

            CREATE TABLE IF NOT EXISTS cache_stats (
                entity_type TEXT PRIMARY KEY,
                hit_count INTEGER DEFAULT 0,
                miss_count INTEGER DEFAULT 0,
                last_hit_at REAL,
                last_miss_at REAL
            );
        """)
        await self._db.commit()

    def _get_ttl(self, entity_type: str) -> int:
        """Get TTL in seconds for an entity type.

        Args:
            entity_type: Type of cached entity.

        Returns:
            TTL in seconds based on entity category.
        """
        category = ENTITY_CATEGORY_MAP.get(entity_type, CacheCategory.METADATA)
        ttl_map = {
            CacheCategory.METADATA: self.settings.cache_ttl_metadata,
            CacheCategory.PROJECTS: self.settings.cache_ttl_projects,
            CacheCategory.AGILE: self.settings.cache_ttl_agile,
            CacheCategory.USERS: self.settings.cache_ttl_users,
        }
        return ttl_map.get(category, self.settings.cache_ttl_metadata)

    @staticmethod
    def make_key(entity_type: str, *parts: str | int) -> str:
        """Create a cache key from entity type and optional parts.

        Args:
            entity_type: Type of entity (e.g., 'issue_types', 'project').
            *parts: Additional key components (e.g., project_key, params_hash).

        Returns:
            Formatted cache key string.

        Example:
            >>> CacheService.make_key("issue_types")
            "issue_types:all"
            >>> CacheService.make_key("project", "PROJ")
            "project:PROJ"
            >>> CacheService.make_key("versions", "PROJ", "abc123")
            "versions:PROJ:abc123"
        """
        if parts:
            return f"{entity_type}:{':'.join(str(p) for p in parts)}"
        return f"{entity_type}:all"

    @staticmethod
    def hash_params(params: dict[str, Any] | None) -> str:
        """Create a hash of query parameters for cache key.

        Args:
            params: Query parameters dict.

        Returns:
            Short hash string of parameters.
        """
        if not params:
            return "default"
        # Sort keys for consistent hashing
        serialized = json.dumps(params, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:12]

    @staticmethod
    def escape_like_pattern(pattern: str) -> str:
        """Escape SQL LIKE wildcards in a pattern.

        Args:
            pattern: The pattern to escape.

        Returns:
            Pattern with % and _ escaped.
        """
        return pattern.replace("%", "\\%").replace("_", "\\_")

    async def get(
        self,
        cache_key: str,
        entity_type: str,
    ) -> dict[str, Any] | list[Any] | None:
        """Get a value from cache if not expired.

        Args:
            cache_key: The cache key to look up.
            entity_type: Entity type for stats tracking.

        Returns:
            Cached value if found and not expired, None otherwise.
        """
        if not self._initialized or not self.settings.cache_enabled:
            return None

        if self._db is None:
            return None

        try:
            now = time.time()
            cursor = await self._db.execute(
                """
                SELECT value FROM cache
                WHERE cache_key = ?
                AND jira_instance = ?
                AND expires_at > ?
                """,
                (cache_key, self.settings.cache_partition_key, now),
            )
            row = await cursor.fetchone()

            if row:
                await self._record_hit(entity_type)
                logger.debug(
                    "Cache hit",
                    extra={"cache_key": cache_key, "entity_type": entity_type},
                )
                return json.loads(row["value"])
            else:
                await self._record_miss(entity_type)
                logger.debug(
                    "Cache miss",
                    extra={"cache_key": cache_key, "entity_type": entity_type},
                )
                return None

        except Exception as e:
            logger.warning(
                "Cache get error",
                extra={"cache_key": cache_key, "error": str(e)},
            )
            return None

    async def set(
        self,
        cache_key: str,
        entity_type: str,
        value: dict[str, Any] | list[Any],
        ttl: int | None = None,
    ) -> None:
        """Store a value in cache.

        Args:
            cache_key: The cache key.
            entity_type: Type of entity being cached.
            value: The value to cache (will be JSON serialized).
            ttl: Optional custom TTL in seconds (uses default for entity_type if not provided).
        """
        if not self._initialized or not self.settings.cache_enabled:
            return

        if self._db is None:
            return

        try:
            now = time.time()
            actual_ttl = ttl if ttl is not None else self._get_ttl(entity_type)
            expires_at = now + actual_ttl

            await self._db.execute(
                """
                INSERT OR REPLACE INTO cache
                (cache_key, entity_type, value, created_at, expires_at, jira_instance)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    entity_type,
                    json.dumps(value),
                    now,
                    expires_at,
                    self.settings.cache_partition_key,
                ),
            )
            await self._db.commit()
            logger.debug(
                "Cache set",
                extra={
                    "cache_key": cache_key,
                    "entity_type": entity_type,
                    "ttl_seconds": actual_ttl,
                },
            )

        except Exception as e:
            logger.warning(
                "Cache set error",
                extra={"cache_key": cache_key, "error": str(e)},
            )

    async def invalidate(
        self,
        cache_key: str | None = None,
        entity_type: str | None = None,
        prefix: str | None = None,
    ) -> int:
        """Invalidate cache entries.

        Args:
            cache_key: Specific key to invalidate.
            entity_type: Invalidate all entries of this type.
            prefix: Invalidate all entries with keys starting with this prefix.

        Returns:
            Number of entries invalidated.
        """
        if not self._initialized or self._db is None:
            return 0

        try:
            cursor: aiosqlite.Cursor
            if cache_key:
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE cache_key = ? AND jira_instance = ?",
                    (cache_key, self.settings.cache_partition_key),
                )
            elif entity_type:
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE entity_type = ? AND jira_instance = ?",
                    (entity_type, self.settings.cache_partition_key),
                )
            elif prefix:
                # Escape LIKE wildcards to prevent unintended matches
                escaped_prefix = self.escape_like_pattern(prefix)
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE cache_key LIKE ? ESCAPE '\\' AND jira_instance = ?",
                    (f"{escaped_prefix}%", self.settings.cache_partition_key),
                )
            else:
                # Invalidate all for this instance
                cursor = await self._db.execute(
                    "DELETE FROM cache WHERE jira_instance = ?",
                    (self.settings.cache_partition_key,),
                )

            await self._db.commit()
            count = cursor.rowcount
            logger.info(
                "Cache invalidated",
                extra={
                    "invalidated_count": count,
                    "cache_key": cache_key,
                    "entity_type": entity_type,
                    "prefix": prefix,
                },
            )
            return count

        except Exception as e:
            logger.warning("Cache invalidate error", extra={"error": str(e)})
            return 0

    async def _record_hit(self, entity_type: str) -> None:
        """Record a cache hit in statistics."""
        if self._db is None:
            return
        try:
            await self._db.execute(
                """
                INSERT INTO cache_stats (entity_type, hit_count, last_hit_at)
                VALUES (?, 1, ?)
                ON CONFLICT(entity_type) DO UPDATE SET
                    hit_count = hit_count + 1,
                    last_hit_at = excluded.last_hit_at
                """,
                (entity_type, time.time()),
            )
            await self._db.commit()
        except Exception:
            pass  # Stats are non-critical

    async def _record_miss(self, entity_type: str) -> None:
        """Record a cache miss in statistics."""
        if self._db is None:
            return
        try:
            await self._db.execute(
                """
                INSERT INTO cache_stats (entity_type, miss_count, last_miss_at)
                VALUES (?, 1, ?)
                ON CONFLICT(entity_type) DO UPDATE SET
                    miss_count = miss_count + 1,
                    last_miss_at = excluded.last_miss_at
                """,
                (entity_type, time.time()),
            )
            await self._db.commit()
        except Exception:
            pass  # Stats are non-critical

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics including hit rates.
        """
        if not self._initialized or self._db is None:
            return {"enabled": False}

        try:
            # Get entry counts
            cursor = await self._db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) as valid,
                    COUNT(DISTINCT entity_type) as entity_types
                FROM cache WHERE jira_instance = ?
                """,
                (time.time(), self.settings.cache_partition_key),
            )
            counts = await cursor.fetchone()

            if counts is None:
                return {"enabled": True, "error": "Failed to get counts"}

            # Get hit/miss stats
            cursor = await self._db.execute("SELECT * FROM cache_stats ORDER BY hit_count DESC")
            stats_rows = await cursor.fetchall()

            stats_by_type: dict[str, dict[str, Any]] = {}
            total_hits = 0
            total_misses = 0

            for row in stats_rows:
                hits = row["hit_count"] or 0
                misses = row["miss_count"] or 0
                total = hits + misses
                stats_by_type[row["entity_type"]] = {
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": round(hits / total * 100, 2) if total > 0 else 0,
                }
                total_hits += hits
                total_misses += misses

            total_requests = total_hits + total_misses

            return {
                "enabled": True,
                "db_path": str(self._db_path),
                "entries": {
                    "total": counts["total"],
                    "valid": counts["valid"],
                    "expired": counts["total"] - counts["valid"],
                    "entity_types": counts["entity_types"],
                },
                "overall": {
                    "hits": total_hits,
                    "misses": total_misses,
                    "hit_rate": (
                        round(total_hits / total_requests * 100, 2) if total_requests > 0 else 0
                    ),
                },
                "by_entity_type": stats_by_type,
            }

        except Exception as e:
            logger.warning("Error getting cache stats", extra={"error": str(e)})
            return {"enabled": True, "error": str(e)}

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed.
        """
        if not self._initialized or self._db is None:
            return 0

        try:
            cursor = await self._db.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (time.time(),),
            )
            await self._db.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info(
                    "Cache cleanup completed",
                    extra={"expired_entries_removed": count},
                )
            return count

        except Exception as e:
            logger.warning("Cache cleanup error", extra={"error": str(e)})
            return 0

    async def _periodic_cleanup(self) -> None:
        """Background task for periodic cache cleanup."""
        while True:
            try:
                await asyncio.sleep(self.settings.cache_cleanup_interval)
                await self.cleanup_expired()

                # Check max entries limit
                if self._db is None:
                    continue

                cursor = await self._db.execute("SELECT COUNT(*) FROM cache")
                row = await cursor.fetchone()
                if row is None:
                    continue

                count = row[0]
                if count > self.settings.cache_max_entries:
                    # Remove oldest entries exceeding limit
                    excess = count - self.settings.cache_max_entries
                    await self._db.execute(
                        """
                        DELETE FROM cache WHERE cache_key IN (
                            SELECT cache_key FROM cache
                            ORDER BY created_at ASC
                            LIMIT ?
                        )
                        """,
                        (excess,),
                    )
                    await self._db.commit()
                    logger.info(
                        "Cache size limit enforced",
                        extra={"removed_entries": excess},
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Periodic cleanup error", extra={"error": str(e)})

    async def close(self) -> None:
        """Close database connection and cleanup.

        Gracefully cancels background tasks with timeout and closes
        the database connection.
        """
        # Cancel cleanup task with timeout
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Cache cleanup task did not cancel within timeout")
            except asyncio.CancelledError:
                pass

        # Close database connection with timeout
        if self._db:
            try:
                await asyncio.wait_for(self._db.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Database close exceeded timeout")
            self._db = None
            self._initialized = False
            logger.debug("Cache service closed")
