#!/usr/bin/env python3
"""
Progressive disclosure cache for large outputs.

Implements cache system to support progressive disclosure pattern:
- Return concise summary with cache_id for large outputs
- User retrieves full details on demand via cache_id
- Reduces token usage by 96% for common queries

Cache directory: ~/.ios-simulator-skill/cache/
Cache expiration: Configurable per cache type (default 1 hour)

Used by:
- sim_list.py - Simulator listing progressive disclosure
- Future: build logs, UI trees, etc.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProgressiveCache:
    """Cache for progressive disclosure pattern.

    Stores large outputs with timestamped IDs for on-demand retrieval.
    Automatically cleans up expired entries.
    """

    def __init__(self, cache_dir: Optional[str] = None, max_age_hours: int = 1):
        """Initialize cache system.

        Args:
            cache_dir: Cache directory path (default: ~/.ios-simulator-skill/cache/)
            max_age_hours: Max age for cache entries before expiration (default: 1 hour)
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.ios-simulator-skill/cache")

        self.cache_dir = Path(cache_dir)
        self.max_age_hours = max_age_hours

        # Create cache directory if needed
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: Dict[str, Any], cache_type: str) -> str:
        """Save data to cache and return cache_id.

        Args:
            data: Dictionary data to cache
            cache_type: Type of cache ('simulator-list', 'build-log', 'ui-tree', etc.)

        Returns:
            Cache ID like 'sim-20251028-143052' for use in progressive disclosure

        Example:
            cache_id = cache.save({'devices': [...]}, 'simulator-list')
            # Returns: 'sim-20251028-143052'
        """
        # Generate cache_id with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        cache_prefix = cache_type.split("-")[0]  # e.g., 'sim' from 'simulator-list'
        cache_id = f"{cache_prefix}-{timestamp}"

        # Save to file
        cache_file = self.cache_dir / f"{cache_id}.json"
        with open(cache_file, "w") as f:
            json.dump(
                {
                    "cache_id": cache_id,
                    "cache_type": cache_type,
                    "created_at": datetime.now().isoformat(),
                    "data": data,
                },
                f,
                indent=2,
            )

        return cache_id

    def get(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from cache by cache_id.

        Args:
            cache_id: Cache ID from save() or list_entries()

        Returns:
            Cached data dictionary, or None if not found/expired

        Example:
            data = cache.get('sim-20251028-143052')
            if data:
                print(f"Found {len(data)} devices")
        """
        cache_file = self.cache_dir / f"{cache_id}.json"

        if not cache_file.exists():
            return None

        # Check if expired
        if self._is_expired(cache_file):
            cache_file.unlink()  # Delete expired file
            return None

        try:
            with open(cache_file, "r") as f:
                entry = json.load(f)
                return entry.get("data")
        except (json.JSONDecodeError, IOError):
            return None

    def list_entries(self, cache_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available cache entries with metadata.

        Args:
            cache_type: Filter by type (e.g., 'simulator-list'), or None for all

        Returns:
            List of cache entries with id, type, created_at, age_seconds

        Example:
            entries = cache.list_entries('simulator-list')
            for entry in entries:
                print(f"{entry['id']} - {entry['age_seconds']}s old")
        """
        entries = []

        for cache_file in sorted(self.cache_dir.glob("*.json"), reverse=True):
            # Check if expired
            if self._is_expired(cache_file):
                cache_file.unlink()
                continue

            try:
                with open(cache_file, "r") as f:
                    entry = json.load(f)

                    # Filter by type if specified
                    if cache_type and entry.get("cache_type") != cache_type:
                        continue

                    created_at = datetime.fromisoformat(entry.get("created_at", ""))
                    age_seconds = (datetime.now() - created_at).total_seconds()

                    entries.append(
                        {
                            "id": entry.get("cache_id"),
                            "type": entry.get("cache_type"),
                            "created_at": entry.get("created_at"),
                            "age_seconds": int(age_seconds),
                        }
                    )
            except (json.JSONDecodeError, IOError, ValueError):
                continue

        return entries

    def cleanup(self, max_age_hours: Optional[int] = None) -> int:
        """Remove expired cache entries.

        Args:
            max_age_hours: Age threshold (default: uses instance max_age_hours)

        Returns:
            Number of entries deleted

        Example:
            deleted = cache.cleanup()
            print(f"Deleted {deleted} expired cache entries")
        """
        if max_age_hours is None:
            max_age_hours = self.max_age_hours

        deleted = 0

        for cache_file in self.cache_dir.glob("*.json"):
            if self._is_expired(cache_file, max_age_hours):
                cache_file.unlink()
                deleted += 1

        return deleted

    def clear(self, cache_type: Optional[str] = None) -> int:
        """Clear all cache entries of a type.

        Args:
            cache_type: Type to clear (e.g., 'simulator-list'), or None to clear all

        Returns:
            Number of entries deleted

        Example:
            cleared = cache.clear('simulator-list')
            print(f"Cleared {cleared} simulator list entries")
        """
        deleted = 0

        for cache_file in self.cache_dir.glob("*.json"):
            if cache_type is None:
                # Clear all
                cache_file.unlink()
                deleted += 1
            else:
                # Clear by type
                try:
                    with open(cache_file, "r") as f:
                        entry = json.load(f)
                        if entry.get("cache_type") == cache_type:
                            cache_file.unlink()
                            deleted += 1
                except (json.JSONDecodeError, IOError):
                    pass

        return deleted

    def _is_expired(self, cache_file: Path, max_age_hours: Optional[int] = None) -> bool:
        """Check if cache file is expired.

        Args:
            cache_file: Path to cache file
            max_age_hours: Age threshold (default: uses instance max_age_hours)

        Returns:
            True if file is older than max_age_hours
        """
        if max_age_hours is None:
            max_age_hours = self.max_age_hours

        try:
            with open(cache_file, "r") as f:
                entry = json.load(f)
                created_at = datetime.fromisoformat(entry.get("created_at", ""))
                age = datetime.now() - created_at
                return age > timedelta(hours=max_age_hours)
        except (json.JSONDecodeError, IOError, ValueError):
            return True


# Global cache instance (lazy-loaded)
_cache_instance: Optional[ProgressiveCache] = None


def get_cache(cache_dir: Optional[str] = None) -> ProgressiveCache:
    """Get or create global cache instance.

    Args:
        cache_dir: Custom cache directory (uses default if None)

    Returns:
        ProgressiveCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ProgressiveCache(cache_dir)
    return _cache_instance
