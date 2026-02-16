#!/usr/bin/env python3
"""
PHASE 2 OPTIMIZATION: Intelligent Caching Layer

Context-aware caching with relationship understanding and TTL-based strategies
for optimal NetBox MCP query performance.
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional, List, Tuple
from cachetools import TTLCache
import threading
import time

logger = logging.getLogger(__name__)


class SmartCache:
    """
    Context-aware caching with relationship understanding.

    Performance Strategy:
    - Static data (manufacturers, device types, sites): Long TTL (30min-1hr)
    - Dynamic data (devices, search results): Short TTL (5min)
    - Failed queries: Medium TTL (10min) to avoid repeated failures
    - Relationship extraction: Pre-populate related caches from query results
    """

    def __init__(self):
        # Static data caches (long TTL) - rarely change
        self.manufacturers_cache = TTLCache(maxsize=100, ttl=3600)      # 1 hour
        self.device_types_cache = TTLCache(maxsize=500, ttl=1800)       # 30 min
        self.device_roles_cache = TTLCache(maxsize=100, ttl=3600)       # 1 hour - PHASE 2.3: Role caching
        self.sites_cache = TTLCache(maxsize=100, ttl=1800)              # 30 min
        self.racks_cache = TTLCache(maxsize=200, ttl=1800)              # 30 min

        # Dynamic data caches (short TTL) - frequently updated
        self.devices_cache = TTLCache(maxsize=1000, ttl=300)            # 5 min
        self.device_search_cache = TTLCache(maxsize=200, ttl=300)       # 5 min
        self.device_list_cache = TTLCache(maxsize=50, ttl=300)          # 5 min

        # Failed query cache (avoid repeated failures)
        self.failed_filters_cache = TTLCache(maxsize=100, ttl=600)      # 10 min

        # Performance tracking
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "failed_queries_avoided": 0,
            "relationship_extractions": 0
        }

        # Thread safety
        self._lock = threading.RLock()

    def _generate_cache_key(self, operation: str, **kwargs) -> str:
        """
        Generate deterministic cache key from operation and parameters.

        Args:
            operation: The type of operation (e.g., "list_devices", "get_device")
            **kwargs: Query parameters

        Returns:
            Deterministic cache key string
        """
        # Sort kwargs for deterministic key generation
        sorted_kwargs = dict(sorted(kwargs.items()))
        key_data = {"op": operation, "params": sorted_kwargs}
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_json.encode()).hexdigest()

    def get_cached_result(self, operation: str, **kwargs) -> Optional[Tuple[Any, str]]:
        """
        Retrieve cached result for the given operation and parameters.

        Args:
            operation: The type of operation
            **kwargs: Query parameters

        Returns:
            Tuple of (cached_result, cache_type) or None if not cached
        """
        cache_key = self._generate_cache_key(operation, **kwargs)

        with self._lock:
            # Check if this is a known failed query
            if cache_key in self.failed_filters_cache:
                self.cache_stats["failed_queries_avoided"] += 1
                logger.debug(f"Avoiding known failed query: {operation} with {kwargs}")
                return None, "failed_query_avoided"

            # Try different cache types based on operation
            cache_mapping = {
                "list_devices": self.device_list_cache,
                "search_devices": self.device_search_cache,
                "get_device": self.devices_cache,
                "list_manufacturers": self.manufacturers_cache,
                "list_device_types": self.device_types_cache,
                "list_device_roles": self.device_roles_cache,        # PHASE 2.3: Role caching
                "list_sites": self.sites_cache,
                "list_racks": self.racks_cache
            }

            cache = cache_mapping.get(operation)
            if cache and cache_key in cache:
                self.cache_stats["hits"] += 1
                logger.debug(f"Cache HIT for {operation}: {cache_key}")
                return cache[cache_key], "cache_hit"

            self.cache_stats["misses"] += 1
            logger.debug(f"Cache MISS for {operation}: {cache_key}")
            return None, "cache_miss"

    def cache_result(self, operation: str, result: Any, **kwargs) -> None:
        """
        Cache the result of an operation and extract relationship data.

        Args:
            operation: The type of operation
            result: The result to cache
            **kwargs: Query parameters used for the operation
        """
        cache_key = self._generate_cache_key(operation, **kwargs)

        with self._lock:
            # Determine which cache to use
            cache_mapping = {
                "list_devices": self.device_list_cache,
                "search_devices": self.device_search_cache,
                "get_device": self.devices_cache,
                "list_manufacturers": self.manufacturers_cache,
                "list_device_types": self.device_types_cache,
                "list_device_roles": self.device_roles_cache,         # PHASE 2.3: Role caching
                "list_sites": self.sites_cache,
                "list_racks": self.racks_cache
            }

            cache = cache_mapping.get(operation)
            if cache:
                cache[cache_key] = result
                logger.debug(f"Cached result for {operation}: {cache_key}")

                # Extract relationship data for pre-population
                if operation in ["list_devices", "search_devices", "get_device"]:
                    self._extract_and_cache_relationships(result)

    def cache_failed_query(self, operation: str, error: str, **kwargs) -> None:
        """
        Cache information about a failed query to avoid repeating it.

        Args:
            operation: The type of operation that failed
            error: Error description
            **kwargs: Query parameters that caused the failure
        """
        cache_key = self._generate_cache_key(operation, **kwargs)

        with self._lock:
            self.failed_filters_cache[cache_key] = {
                "error": error,
                "timestamp": time.time(),
                "operation": operation,
                "params": kwargs
            }
            logger.debug(f"Cached failed query: {operation} - {error}")

    def _extract_and_cache_relationships(self, result: Any) -> None:
        """
        Extract relationship data from query results and pre-populate caches.

        This reduces future API calls by caching related objects found in responses.

        Args:
            result: Query result containing device data
        """
        try:
            devices = []

            # Handle different result formats
            if isinstance(result, dict):
                if "devices" in result:
                    devices = result["devices"]
                elif isinstance(result.get("data"), list):
                    devices = result["data"]
            elif isinstance(result, list):
                devices = result

            # Extract and cache relationship data
            for device in devices:
                if not isinstance(device, dict):
                    continue

                # Cache manufacturer data
                device_type = device.get("device_type")
                if isinstance(device_type, dict):
                    manufacturer = device_type.get("manufacturer")
                    if isinstance(manufacturer, dict) and "name" in manufacturer:
                        mfg_key = self._generate_cache_key("get_manufacturer", name=manufacturer["name"])
                        self.manufacturers_cache[mfg_key] = manufacturer

                # Cache site data
                site = device.get("site")
                if isinstance(site, dict) and "name" in site:
                    site_key = self._generate_cache_key("get_site", name=site["name"])
                    self.sites_cache[site_key] = site

                # Cache rack data
                rack = device.get("rack")
                if isinstance(rack, dict) and "name" in rack:
                    rack_key = self._generate_cache_key("get_rack", name=rack["name"])
                    self.racks_cache[rack_key] = rack

                # Cache device type data
                if isinstance(device_type, dict) and "model" in device_type:
                    dt_key = self._generate_cache_key("get_device_type", model=device_type["model"])
                    self.device_types_cache[dt_key] = device_type

                # PHASE 2.3: Cache device role data
                role = device.get("role")
                if isinstance(role, dict) and "slug" in role:
                    role_key = self._generate_cache_key("get_device_role", slug=role["slug"])
                    self.device_roles_cache[role_key] = role

            if devices:
                self.cache_stats["relationship_extractions"] += 1
                logger.debug(f"Extracted relationships from {len(devices)} devices")

        except Exception as e:
            logger.warning(f"Failed to extract relationships from result: {e}")

    def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """
        Clear specified cache or all caches.

        Args:
            cache_type: Specific cache to clear, or None to clear all
        """
        with self._lock:
            if cache_type == "manufacturers":
                self.manufacturers_cache.clear()
            elif cache_type == "device_types":
                self.device_types_cache.clear()
            elif cache_type == "sites":
                self.sites_cache.clear()
            elif cache_type == "racks":
                self.racks_cache.clear()
            elif cache_type == "devices":
                self.devices_cache.clear()
                self.device_search_cache.clear()
                self.device_list_cache.clear()
            elif cache_type == "failed_queries":
                self.failed_filters_cache.clear()
            else:
                # Clear all caches
                self.manufacturers_cache.clear()
                self.device_types_cache.clear()
                self.sites_cache.clear()
                self.racks_cache.clear()
                self.devices_cache.clear()
                self.device_search_cache.clear()
                self.device_list_cache.clear()
                self.failed_filters_cache.clear()

        logger.info(f"Cleared cache: {cache_type or 'all'}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get current cache performance statistics.

        Returns:
            Dictionary containing cache performance metrics
        """
        with self._lock:
            stats = self.cache_stats.copy()

            # Calculate hit rate
            total_requests = stats["hits"] + stats["misses"]
            hit_rate = (stats["hits"] / total_requests * 100) if total_requests > 0 else 0

            # Add cache sizes
            stats.update({
                "hit_rate_percentage": round(hit_rate, 2),
                "total_requests": total_requests,
                "cache_sizes": {
                    "manufacturers": len(self.manufacturers_cache),
                    "device_types": len(self.device_types_cache),
                    "sites": len(self.sites_cache),
                    "racks": len(self.racks_cache),
                    "devices": len(self.devices_cache),
                    "device_search": len(self.device_search_cache),
                    "device_list": len(self.device_list_cache),
                    "failed_queries": len(self.failed_filters_cache)
                }
            })

            return stats

    def warm_cache(self, client, priority_operations: Optional[List[str]] = None) -> None:
        """
        Pre-warm cache with commonly accessed data.

        Args:
            client: NetBox client instance
            priority_operations: List of operations to prioritize for warming
        """
        try:
            default_operations = ["list_manufacturers", "list_sites", "list_device_types"]
            operations = priority_operations or default_operations

            logger.info(f"Warming cache with operations: {operations}")

            for operation in operations:
                try:
                    if operation == "list_manufacturers" and not self.manufacturers_cache:
                        manufacturers = list(client.dcim.manufacturers.all())
                        self.cache_result("list_manufacturers", manufacturers)

                    elif operation == "list_sites" and not self.sites_cache:
                        sites = list(client.dcim.sites.all())
                        self.cache_result("list_sites", sites)

                    elif operation == "list_device_types" and not self.device_types_cache:
                        device_types = list(client.dcim.device_types.all())
                        self.cache_result("list_device_types", device_types)

                except Exception as e:
                    logger.warning(f"Failed to warm cache for {operation}: {e}")
                    self.cache_failed_query(operation, str(e))

            logger.info("Cache warming completed")

        except Exception as e:
            logger.error(f"Cache warming failed: {e}")


# Global cache instance
_global_cache: Optional[SmartCache] = None
_cache_lock = threading.Lock()


def get_cache() -> SmartCache:
    """
    Get or create the global cache instance (singleton pattern).

    Returns:
        Global SmartCache instance
    """
    global _global_cache

    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = SmartCache()
                logger.info("Initialized global SmartCache instance")

    return _global_cache


def cache_enabled_operation(operation_name: str):
    """
    Decorator to add caching to any operation.

    Usage:
        @cache_enabled_operation("list_devices")
        def my_device_function(client, **kwargs):
            return expensive_api_call(client, **kwargs)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Try to get cached result
            cached_result, cache_type = cache.get_cached_result(operation_name, **kwargs)
            if cached_result is not None:
                return cached_result

            try:
                # Execute the actual operation
                result = func(*args, **kwargs)

                # Cache the successful result
                cache.cache_result(operation_name, result, **kwargs)

                return result

            except Exception as e:
                # Cache the failed operation
                cache.cache_failed_query(operation_name, str(e), **kwargs)
                raise

        return wrapper
    return decorator