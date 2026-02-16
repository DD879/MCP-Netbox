"""
NetBox MCP Performance Monitoring and Metrics System.

This module provides comprehensive performance monitoring, metrics collection,
and health checking for the NetBox MCP server. It tracks operation times,
cache performance, system resources, and provides dashboard functionality.
"""

import asyncio
import json
import logging
import psutil
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
import csv
import io

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a single operation execution."""
    
    operation_name: str
    duration: float
    success: bool
    timestamp: datetime
    error_details: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    cache_hit: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    
    hits: int
    misses: int
    hit_ratio: float
    cache_size_mb: float
    evictions: int
    timestamp: datetime
    
    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.hits + self.misses
    
    @classmethod
    def calculate(cls, hits: int, misses: int, cache_size_bytes: int, evictions: int) -> 'CacheMetrics':
        """Calculate cache metrics from raw data."""
        total_requests = hits + misses
        hit_ratio = hits / total_requests if total_requests > 0 else 0.0
        cache_size_mb = cache_size_bytes / (1024 * 1024)
        
        return cls(
            hits=hits,
            misses=misses,
            hit_ratio=hit_ratio,
            cache_size_mb=cache_size_mb,
            evictions=evictions,
            timestamp=datetime.now()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    
    cpu_usage: float
    memory_usage: float  # MB
    memory_available: float  # MB
    active_connections: int
    request_queue_size: int
    timestamp: datetime
    disk_usage: Optional[float] = None  # MB
    network_io: Optional[Dict[str, float]] = None
    
    @property
    def memory_usage_percentage(self) -> float:
        """Calculate memory usage percentage."""
        total_memory = self.memory_usage + self.memory_available
        return (self.memory_usage / total_memory) * 100 if total_memory > 0 else 0.0
    
    @classmethod
    def collect(cls) -> 'SystemMetrics':
        """Collect current system metrics."""
        try:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            # Convert bytes to MB
            memory_usage = memory.used / (1024 * 1024)
            memory_available = memory.available / (1024 * 1024)
            
            # Get network connections count (approximation)
            try:
                active_connections = len(psutil.net_connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                active_connections = 0
            
            return cls(
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                memory_available=memory_available,
                active_connections=active_connections,
                request_queue_size=0,  # Would need framework integration
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")
            return cls(
                cpu_usage=0.0,
                memory_usage=0.0,
                memory_available=0.0,
                active_connections=0,
                request_queue_size=0,
                timestamp=datetime.now()
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class PerformanceMonitor:
    """Main performance monitoring class."""
    
    def __init__(self, max_history_size: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            max_history_size: Maximum number of metrics to keep in memory
        """
        self.max_history_size = max_history_size
        self.enabled = True
        self._lock = threading.RLock()
        
        # Metrics storage
        self._metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history_size))
        self._operation_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        logger.info(f"Performance monitor initialized with max_history_size={max_history_size}")
    
    @contextmanager
    def time_operation(self, operation_name: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Context manager for timing operations.
        
        Args:
            operation_name: Name of the operation being timed
            parameters: Optional parameters passed to the operation
        
        Example:
            with monitor.time_operation("netbox_create_device", {"name": "server-01"}):
                # Operation code here
                pass
        """
        if not self.enabled:
            yield
            return
        
        start_time = time.time()
        success = True
        error_details = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_details = {
                "error_type": type(e).__name__,
                "message": str(e)
            }
            raise
        finally:
            duration = time.time() - start_time
            
            metrics = OperationMetrics(
                operation_name=operation_name,
                duration=duration,
                success=success,
                timestamp=datetime.now(),
                error_details=error_details,
                parameters=parameters
            )
            
            self._record_operation_metrics(metrics)
    
    def _record_operation_metrics(self, metrics: OperationMetrics):
        """Record operation metrics."""
        with self._lock:
            self._metrics_history[metrics.operation_name].append(metrics)
            self._update_operation_stats(metrics)
    
    def _update_operation_stats(self, metrics: OperationMetrics):
        """Update aggregated operation statistics."""
        op_name = metrics.operation_name
        stats = self._operation_stats[op_name]
        
        # Initialize stats if first operation
        if not stats:
            stats.update({
                "total_operations": 0,
                "successful_operations": 0,
                "total_duration": 0.0,
                "min_duration": float('inf'),
                "max_duration": 0.0,
                "last_execution": None
            })
        
        # Update stats
        stats["total_operations"] += 1
        stats["total_duration"] += metrics.duration
        stats["min_duration"] = min(stats["min_duration"], metrics.duration)
        stats["max_duration"] = max(stats["max_duration"], metrics.duration)
        stats["last_execution"] = metrics.timestamp
        
        if metrics.success:
            stats["successful_operations"] += 1
    
    def get_operation_history(self, operation_name: str) -> List[OperationMetrics]:
        """Get operation history for a specific operation."""
        with self._lock:
            return list(self._metrics_history[operation_name])
    
    def get_operation_statistics(self, operation_name: str) -> Dict[str, Any]:
        """Get aggregated statistics for an operation."""
        with self._lock:
            stats = self._operation_stats[operation_name].copy()
            
            if stats.get("total_operations", 0) > 0:
                stats["success_rate"] = stats["successful_operations"] / stats["total_operations"]
                stats["average_duration"] = stats["total_duration"] / stats["total_operations"]
                
                # Convert min_duration from inf if no operations
                if stats["min_duration"] == float('inf'):
                    stats["min_duration"] = 0.0
            else:
                stats.update({
                    "success_rate": 0.0,
                    "average_duration": 0.0,
                    "min_duration": 0.0,
                    "max_duration": 0.0
                })
            
            return stats
    
    def get_all_operations_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary statistics for all operations."""
        summary = {}
        for operation_name in self._operation_stats:
            summary[operation_name] = self.get_operation_statistics(operation_name)
        return summary
    
    def record_cache_metrics(self, metrics: CacheMetrics):
        """Record cache performance metrics."""
        if not self.enabled:
            return
        
        with self._lock:
            self._metrics_history["cache_metrics"].append(metrics)
    
    def record_system_metrics(self, metrics: SystemMetrics):
        """Record system performance metrics."""
        if not self.enabled:
            return
        
        with self._lock:
            self._metrics_history["system_metrics"].append(metrics)
    
    def get_latest_cache_metrics(self) -> Optional[CacheMetrics]:
        """Get the latest cache metrics."""
        with self._lock:
            cache_history = self._metrics_history["cache_metrics"]
            return cache_history[-1] if cache_history else None
    
    def get_latest_system_metrics(self) -> Optional[SystemMetrics]:
        """Get the latest system metrics."""
        with self._lock:
            system_history = self._metrics_history["system_metrics"]
            return system_history[-1] if system_history else None
    
    def clear_history(self):
        """Clear all metrics history."""
        with self._lock:
            self._metrics_history.clear()
            self._operation_stats.clear()
        
        logger.info("Performance monitor history cleared")


class MetricsCollector:
    """Automatic metrics collector."""
    
    def __init__(self, performance_monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize metrics collector.
        
        Args:
            performance_monitor: Performance monitor instance
        """
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self._collection_interval = 60  # seconds
        self._collection_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.is_running = False
        
        logger.info(f"Metrics collector initialized with interval={self._collection_interval}s")
    
    def start_collection(self):
        """Start automatic metrics collection."""
        if self.is_running:
            logger.warning("Metrics collection already running")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        # Start collection in background
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._collection_task = loop.create_task(self._collection_loop())
            else:
                # This should be started from an async context where the loop is already running
                # For example, in a FastAPI startup event or ASGI server startup
                raise RuntimeError("MetricsCollector must be started from a running event loop. "
                                 "Start the collector from an async context like a FastAPI startup event.")
        except RuntimeError as e:
            logger.error(f"Failed to start metrics collection: {e}")
            self.is_running = False
            raise
        
        logger.info("Metrics collection started")
    
    def stop_collection(self):
        """Stop automatic metrics collection."""
        if not self.is_running:
            return
        
        self.is_running = False
        self._stop_event.set()
        
        if self._collection_task:
            self._collection_task.cancel()
        
        logger.info("Metrics collection stopped")
    
    async def _collection_loop(self):
        """Background collection loop."""
        while not self._stop_event.is_set():
            try:
                self.collect_metrics()
                await asyncio.sleep(self._collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    def collect_metrics(self):
        """Collect current metrics."""
        start_time = time.time()
        
        try:
            # Collect system metrics
            system_metrics = SystemMetrics.collect()
            self.performance_monitor.record_system_metrics(system_metrics)
            
            # Collect cache metrics (would integrate with actual cache)
            # This is a placeholder - would get real cache stats
            cache_metrics = CacheMetrics(
                hits=0,
                misses=0,
                hit_ratio=0.0,
                cache_size_mb=0.0,
                evictions=0,
                timestamp=datetime.now()
            )
            self.performance_monitor.record_cache_metrics(cache_metrics)
            
            collection_duration = time.time() - start_time
            logger.debug(f"Metrics collection completed in {collection_duration:.3f}s")
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "collection_duration": 0.0,
            "operation_count": len(self.performance_monitor._operation_stats),
            "system_metrics": None,
            "cache_metrics": None
        }
        
        # Add latest metrics
        latest_system = self.performance_monitor.get_latest_system_metrics()
        if latest_system:
            summary["system_metrics"] = latest_system.to_dict()
        
        latest_cache = self.performance_monitor.get_latest_cache_metrics()
        if latest_cache:
            summary["cache_metrics"] = latest_cache.to_dict()
        
        return summary
    
    def export_metrics(self) -> Dict[str, Any]:
        """Export all collected metrics."""
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "system_metrics": [],
            "cache_metrics": [],
            "operation_metrics": {}
        }
        
        # Export system metrics
        system_history = self.performance_monitor._metrics_history["system_metrics"]
        export_data["system_metrics"] = [m.to_dict() for m in system_history]
        
        # Export cache metrics
        cache_history = self.performance_monitor._metrics_history["cache_metrics"]
        export_data["cache_metrics"] = [m.to_dict() for m in cache_history]
        
        # Export operation metrics
        for op_name, history in self.performance_monitor._metrics_history.items():
            if op_name not in ["system_metrics", "cache_metrics"]:
                export_data["operation_metrics"][op_name] = [m.to_dict() for m in history]
        
        return export_data
    
    def reset_metrics(self):
        """Reset all collected metrics."""
        self.performance_monitor.clear_history()
        logger.info("All metrics reset")


class HealthCheck:
    """System health check functionality."""
    
    def __init__(self, performance_monitor: Optional[PerformanceMonitor] = None):
        """
        Initialize health check.
        
        Args:
            performance_monitor: Performance monitor instance
        """
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.netbox_client = None  # Will be set by dependency injection
        
        # Health check thresholds
        self._thresholds = {
            "cpu_usage_warning": 70.0,
            "cpu_usage_critical": 90.0,
            "memory_usage_warning": 80.0,
            "memory_usage_critical": 95.0,
            "cache_hit_ratio_warning": 0.7,
            "cache_hit_ratio_critical": 0.5,
            "response_time_warning": 2.0,  # seconds
            "response_time_critical": 5.0
        }
        
        # Custom health checks
        self._checks: Dict[str, Callable] = {}
        
        logger.info("Health check system initialized")
    
    def register_check(self, name: str, check_function: Callable) -> None:
        """
        Register a custom health check.
        
        Args:
            name: Name of the health check
            check_function: Function that returns health status dict
        """
        self._checks[name] = check_function
        logger.info(f"Registered custom health check: {name}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        # Standard health checks
        checks = [
            ("system_resources", self._check_system_resources),
            ("cache_performance", self._check_cache_performance),
            ("operation_performance", self._check_operation_performance),
            ("netbox_connectivity", self._check_netbox_connectivity)
        ]
        
        # Add custom checks
        for name, check_func in self._checks.items():
            checks.append((name, check_func))
        
        # Run all checks
        overall_status = "healthy"
        for check_name, check_func in checks:
            try:
                check_result = check_func()
                health_status["checks"][check_name] = check_result
                
                # Update overall status based on worst individual status
                check_status = check_result.get("status", "healthy")
                if check_status == "critical":
                    overall_status = "critical"
                elif check_status == "warning" and overall_status != "critical":
                    overall_status = "warning"
                    
            except Exception as e:
                logger.error(f"Health check '{check_name}' failed: {e}")
                health_status["checks"][check_name] = {
                    "status": "critical",
                    "message": f"Health check failed: {e}",
                    "timestamp": datetime.now().isoformat()
                }
                overall_status = "critical"
        
        health_status["overall_status"] = overall_status
        return health_status
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            metrics = SystemMetrics.collect()
            
            status = "healthy"
            messages = []
            
            # Check CPU usage
            if metrics.cpu_usage >= self._thresholds["cpu_usage_critical"]:
                status = "critical"
                messages.append(f"CPU usage critical: {metrics.cpu_usage:.1f}%")
            elif metrics.cpu_usage >= self._thresholds["cpu_usage_warning"]:
                status = "warning"
                messages.append(f"CPU usage high: {metrics.cpu_usage:.1f}%")
            
            # Check memory usage
            memory_percentage = metrics.memory_usage_percentage
            if memory_percentage >= self._thresholds["memory_usage_critical"]:
                status = "critical"
                messages.append(f"Memory usage critical: {memory_percentage:.1f}%")
            elif memory_percentage >= self._thresholds["memory_usage_warning"]:
                if status != "critical":
                    status = "warning"
                messages.append(f"Memory usage high: {memory_percentage:.1f}%")
            
            return {
                "status": status,
                "message": "; ".join(messages) if messages else "System resources normal",
                "details": {
                    "cpu_usage": metrics.cpu_usage,
                    "memory_usage_percentage": memory_percentage,
                    "active_connections": metrics.active_connections
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Failed to check system resources: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _check_cache_performance(self) -> Dict[str, Any]:
        """Check cache performance."""
        try:
            cache_metrics = self.performance_monitor.get_latest_cache_metrics()
            
            if not cache_metrics:
                return {
                    "status": "warning",
                    "message": "No cache metrics available",
                    "timestamp": datetime.now().isoformat()
                }
            
            status = "healthy"
            messages = []
            
            # Check hit ratio
            if cache_metrics.hit_ratio <= self._thresholds["cache_hit_ratio_critical"]:
                status = "critical"
                messages.append(f"Cache hit ratio critical: {cache_metrics.hit_ratio:.2%}")
            elif cache_metrics.hit_ratio <= self._thresholds["cache_hit_ratio_warning"]:
                status = "warning"
                messages.append(f"Cache hit ratio low: {cache_metrics.hit_ratio:.2%}")
            
            return {
                "status": status,
                "message": "; ".join(messages) if messages else "Cache performance normal",
                "details": {
                    "hit_ratio": cache_metrics.hit_ratio,
                    "cache_size_mb": cache_metrics.cache_size_mb,
                    "total_requests": cache_metrics.total_requests
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Failed to check cache performance: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _check_operation_performance(self) -> Dict[str, Any]:
        """Check operation performance."""
        try:
            all_stats = self.performance_monitor.get_all_operations_summary()
            
            if not all_stats:
                return {
                    "status": "healthy",
                    "message": "No operation metrics available",
                    "timestamp": datetime.now().isoformat()
                }
            
            status = "healthy"
            messages = []
            slow_operations = []
            
            # Check for slow operations
            for op_name, stats in all_stats.items():
                avg_duration = stats.get("average_duration", 0)
                
                if avg_duration >= self._thresholds["response_time_critical"]:
                    status = "critical"
                    slow_operations.append(f"{op_name}: {avg_duration:.2f}s")
                elif avg_duration >= self._thresholds["response_time_warning"]:
                    if status != "critical":
                        status = "warning"
                    slow_operations.append(f"{op_name}: {avg_duration:.2f}s")
            
            if slow_operations:
                messages.append(f"Slow operations detected: {', '.join(slow_operations)}")
            
            return {
                "status": status,
                "message": "; ".join(messages) if messages else "Operation performance normal",
                "details": {
                    "total_operations": len(all_stats),
                    "slow_operations": len(slow_operations)
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Failed to check operation performance: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _check_netbox_connectivity(self) -> Dict[str, Any]:
        """Check NetBox connectivity."""
        try:
            if not self.netbox_client:
                return {
                    "status": "warning",
                    "message": "NetBox client not configured",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Perform an actual health check using the client
            import time
            start_time = time.time()
            
            try:
                # Try to fetch a small amount of data to test connectivity
                sites = self.netbox_client.dcim.sites.filter(limit=1)
                response_time_ms = round((time.time() - start_time) * 1000, 2)
                
                return {
                    "status": "healthy",
                    "message": "NetBox connectivity normal",
                    "details": {
                        "connected": True,
                        "response_time_ms": response_time_ms,
                        "test_endpoint": "dcim.sites"
                    },
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as conn_error:
                response_time_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "status": "critical",
                    "message": f"NetBox connectivity failed: {str(conn_error)}",
                    "details": {
                        "connected": False,
                        "response_time_ms": response_time_ms,
                        "error": str(conn_error)
                    },
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            return {
                "status": "critical",
                "message": f"NetBox connectivity failed: {e}",
                "timestamp": datetime.now().isoformat()
            }


class MetricsDashboard:
    """Metrics dashboard for visualization and reporting."""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize metrics dashboard.
        
        Args:
            metrics_collector: Metrics collector instance
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.health_check = HealthCheck(self.metrics_collector.performance_monitor)
        
        logger.info("Metrics dashboard initialized")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "overview": self._get_overview(),
            "operation_metrics": self._get_operation_metrics(),
            "cache_metrics": self._get_cache_metrics(),
            "system_metrics": self._get_system_metrics(),
            "health_status": self.health_check.get_health_status()
        }
        
        return dashboard_data
    
    def _get_overview(self) -> Dict[str, Any]:
        """Get overview statistics."""
        monitor = self.metrics_collector.performance_monitor
        all_stats = monitor.get_all_operations_summary()
        
        # Calculate overview metrics
        total_operations = sum(stats.get("total_operations", 0) for stats in all_stats.values())
        total_successful = sum(stats.get("successful_operations", 0) for stats in all_stats.values())
        
        success_rate = total_successful / total_operations if total_operations > 0 else 0.0
        
        # Get average response time
        avg_durations = [stats.get("average_duration", 0) for stats in all_stats.values() if stats.get("average_duration", 0) > 0]
        avg_response_time = sum(avg_durations) / len(avg_durations) if avg_durations else 0.0
        
        return {
            "total_operations": total_operations,
            "success_rate": success_rate,
            "average_response_time": avg_response_time,
            "active_operations": len(all_stats),
            "uptime": "N/A"  # Would track actual uptime
        }
    
    def _get_operation_metrics(self) -> List[Dict[str, Any]]:
        """Get operation metrics for dashboard."""
        monitor = self.metrics_collector.performance_monitor
        all_stats = monitor.get_all_operations_summary()
        
        operation_metrics = []
        for op_name, stats in all_stats.items():
            operation_metrics.append({
                "operation_name": op_name,
                "total_executions": stats.get("total_operations", 0),
                "success_rate": stats.get("success_rate", 0.0),
                "average_duration": stats.get("average_duration", 0.0),
                "min_duration": stats.get("min_duration", 0.0),
                "max_duration": stats.get("max_duration", 0.0),
                "last_execution": stats.get("last_execution", {}).isoformat() if stats.get("last_execution") else None
            })
        
        # Sort by total executions
        operation_metrics.sort(key=lambda x: x["total_executions"], reverse=True)
        
        return operation_metrics
    
    def _get_cache_metrics(self) -> Optional[Dict[str, Any]]:
        """Get cache metrics for dashboard."""
        cache_metrics = self.metrics_collector.performance_monitor.get_latest_cache_metrics()
        
        if cache_metrics:
            return cache_metrics.to_dict()
        return None
    
    def _get_system_metrics(self) -> Optional[Dict[str, Any]]:
        """Get system metrics for dashboard."""
        system_metrics = self.metrics_collector.performance_monitor.get_latest_system_metrics()
        
        if system_metrics:
            return system_metrics.to_dict()
        return None
    
    def get_time_series_data(self, metric_type: str, duration_minutes: int = 60) -> Dict[str, Any]:
        """
        Get time series data for charts.
        
        Args:
            metric_type: Type of metrics (system_metrics, cache_metrics, etc.)
            duration_minutes: Duration of data to retrieve
        
        Returns:
            Time series data for charting
        """
        monitor = self.metrics_collector.performance_monitor
        history = monitor._metrics_history.get(metric_type, [])
        
        # Filter by time range
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        filtered_history = [m for m in history if m.timestamp >= cutoff_time]
        
        timestamps = [m.timestamp.isoformat() for m in filtered_history]
        data_points = [m.to_dict() for m in filtered_history]
        
        return {
            "timestamps": timestamps,
            "data_points": data_points,
            "metric_type": metric_type,
            "duration_minutes": duration_minutes
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for dashboard."""
        overview = self._get_overview()
        operation_metrics = self._get_operation_metrics()
        
        # Get most frequent operations
        most_frequent = operation_metrics[:5] if operation_metrics else []
        
        return {
            "total_operations": overview["total_operations"],
            "average_response_time": overview["average_response_time"],
            "success_rate": overview["success_rate"],
            "most_frequent_operations": most_frequent
        }
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts based on health checks."""
        health_status = self.health_check.get_health_status()
        alerts = []
        
        for check_name, check_result in health_status["checks"].items():
            status = check_result.get("status", "healthy")
            
            if status in ["warning", "critical"]:
                alerts.append({
                    "check_name": check_name,
                    "severity": status,
                    "message": check_result.get("message", ""),
                    "timestamp": check_result.get("timestamp", datetime.now().isoformat())
                })
        
        # Sort by severity
        severity_order = {"critical": 0, "warning": 1}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 2))
        
        return alerts
    
    def export_data(self, format: str = "json") -> str:
        """
        Export dashboard data in specified format.
        
        Args:
            format: Export format ("json" or "csv")
        
        Returns:
            Exported data as string
        """
        dashboard_data = self.get_dashboard_data()
        
        if format.lower() == "json":
            return json.dumps(dashboard_data, indent=2, default=str)
        
        elif format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write operation metrics as CSV
            writer.writerow(["Operation", "Total Executions", "Success Rate", "Avg Duration", "Min Duration", "Max Duration"])
            
            for metric in dashboard_data["operation_metrics"]:
                writer.writerow([
                    metric["operation_name"],
                    metric["total_executions"],
                    f"{metric['success_rate']:.2%}",
                    f"{metric['average_duration']:.3f}",
                    f"{metric['min_duration']:.3f}",
                    f"{metric['max_duration']:.3f}"
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global performance monitor instance
_global_monitor: Optional[PerformanceMonitor] = None
_monitor_lock = threading.Lock()


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance (singleton)."""
    global _global_monitor
    
    if _global_monitor is None:
        with _monitor_lock:
            if _global_monitor is None:
                _global_monitor = PerformanceMonitor()
    
    return _global_monitor


# Decorator for monitoring function performance
def monitor_performance(operation_name: Optional[str] = None):
    """
    Decorator to monitor function performance.
    
    Args:
        operation_name: Custom operation name (defaults to function name)
    
    Example:
        @monitor_performance("netbox_create_device")
        def create_device(name: str) -> Dict[str, Any]:
            # Function implementation
            pass
    """
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = func.__name__
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                monitor = get_performance_monitor()
                with monitor.time_operation(operation_name, kwargs):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                monitor = get_performance_monitor()
                with monitor.time_operation(operation_name, kwargs):
                    return func(*args, **kwargs)
            return sync_wrapper
    
    return decorator