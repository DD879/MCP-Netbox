#!/usr/bin/env python3
"""
NetBox MCP Asynchronous Task Definitions

Implements Redis Queue (RQ) based task system for long-running bulk operations.
Based on Gemini's Phase 3 architectural guidance for enterprise-scale performance.
"""

import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import logging

try:
    from rq import Queue, get_current_job
    from redis import Redis
    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False

from .client import NetBoxClient, NetBoxBulkOrchestrator
from .config import NetBoxConfig

logger = logging.getLogger(__name__)


class TaskError(Exception):
    """Custom exception for task-related errors."""
    pass


class TaskTracker:
    """
    Task progress tracking and status management using Redis.
    
    Provides centralized task status storage with TTL and real-time updates.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize task tracker with Redis connection.
        
        Args:
            redis_url: Redis connection URL
        """
        if not RQ_AVAILABLE:
            raise TaskError("Redis Queue (RQ) not available. Install with: pip install rq redis")
        
        self.redis_conn = Redis.from_url(redis_url)
        self.task_ttl = 3600  # 1 hour task data retention
        
        logger.info(f"TaskTracker initialized with Redis: {redis_url}")
    
    def update_task_status(self, task_id: str, status: str, data: Dict[str, Any]):
        """
        Update task status and progress in Redis.
        
        Args:
            task_id: Unique task identifier
            status: Task status (queued, running, completed, failed)
            data: Additional task data and progress information
        """
        task_data = {
            "task_id": task_id,
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
            **data
        }
        
        # Store with TTL
        self.redis_conn.setex(
            f"task:{task_id}", 
            self.task_ttl, 
            json.dumps(task_data, default=str)
        )
        
        logger.info(f"Task {task_id} status updated: {status}")
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve current task status from Redis.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status data or not_found status
        """
        task_data = self.redis_conn.get(f"task:{task_id}")
        if task_data:
            return json.loads(task_data)
        return {"status": "not_found", "error": "Task not found or expired"}
    
    def list_active_tasks(self) -> List[Dict[str, Any]]:
        """
        List all currently active tasks.
        
        Returns:
            List of active task status data
        """
        task_keys = self.redis_conn.keys("task:*")
        tasks = []
        for key in task_keys:
            task_data = self.redis_conn.get(key)
            if task_data:
                try:
                    tasks.append(json.loads(task_data))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode task data for key: {key}")
        
        # Sort by updated_at descending
        tasks.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return tasks
    
    def cleanup_expired_tasks(self):
        """Clean up expired task entries (called by Redis TTL automatically)."""
        # TTL handles cleanup automatically, but this method can be used for manual cleanup
        expired_keys = []
        task_keys = self.redis_conn.keys("task:*")
        
        for key in task_keys:
            ttl = self.redis_conn.ttl(key)
            if ttl == -2:  # Key doesn't exist
                expired_keys.append(key)
            elif ttl == -1:  # Key exists but no TTL
                # Set TTL for keys without expiration
                self.redis_conn.expire(key, self.task_ttl)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired task keys")


class AsyncTaskManager:
    """
    Manager for asynchronous task queue operations.
    
    Handles task queueing, worker management, and integration with NetBox operations.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", queue_name: str = "netbox_bulk"):
        """
        Initialize async task manager.
        
        Args:
            redis_url: Redis connection URL
            queue_name: RQ queue name for NetBox operations
        """
        if not RQ_AVAILABLE:
            raise TaskError("Redis Queue (RQ) not available. Install with: pip install rq redis")
        
        self.redis_conn = Redis.from_url(redis_url)
        self.queue = Queue(queue_name, connection=self.redis_conn)
        self.tracker = TaskTracker(redis_url)
        
        logger.info(f"AsyncTaskManager initialized - Queue: {queue_name}")
    
    def generate_task_id(self, operation_type: str, additional_info: str = "") -> str:
        """
        Generate unique task ID.
        
        Args:
            operation_type: Type of operation (e.g., bulk_devices, enterprise_sync)
            additional_info: Additional identifier information
            
        Returns:
            Unique task identifier
        """
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        if additional_info:
            return f"{operation_type}_{additional_info}_{timestamp}_{unique_id}"
        else:
            return f"{operation_type}_{timestamp}_{unique_id}"
    
    def queue_bulk_device_operation(
        self, 
        devices_data: List[Dict[str, Any]], 
        config: Dict[str, Any],
        timeout: int = 3600
    ) -> str:
        """
        Queue bulk device operation for background processing.
        
        Args:
            devices_data: List of device data for processing
            config: Operation configuration (confirm, dry_run, etc.)
            timeout: Task timeout in seconds
            
        Returns:
            Task ID for progress tracking
        """
        task_id = self.generate_task_id("bulk_devices", f"{len(devices_data)}dev")
        
        # Initialize task status
        self.tracker.update_task_status(task_id, "queued", {
            "operation_type": "bulk_device_operation",
            "device_count": len(devices_data),
            "queued_at": datetime.utcnow().isoformat(),
            "progress": 0,
            "config": config
        })
        
        # Queue the background task
        job = self.queue.enqueue(
            execute_bulk_device_operation,
            task_id,
            devices_data,
            config,
            timeout=timeout,
            job_id=task_id
        )
        
        logger.info(f"Queued bulk device operation: {task_id} ({len(devices_data)} devices)")
        return task_id
    
    def get_queue_info(self) -> Dict[str, Any]:
        """
        Get current queue status and statistics.
        
        Returns:
            Queue information and statistics
        """
        return {
            "queue_name": self.queue.name,
            "job_count": len(self.queue),
            "failed_job_count": len(self.queue.failed_job_registry),
            "worker_count": len(self.queue.connection.smembers(self.queue.connection._key(f"{self.queue.key}:workers"))),
            "redis_info": {
                "connected": self.redis_conn.ping(),
                "memory_usage": self.redis_conn.info().get("used_memory_human", "unknown")
            }
        }


def execute_bulk_device_operation(
    task_id: str, 
    devices_data: List[Dict[str, Any]], 
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Background task for bulk device operations using two-pass strategy.
    
    This function runs in the RQ worker process and should not be called directly.
    Use AsyncTaskManager.queue_bulk_device_operation() instead.
    
    Args:
        task_id: Unique task identifier for progress tracking
        devices_data: Device data for bulk processing
        config: Operation configuration and options
        
    Returns:
        Final operation results
        
    Raises:
        TaskError: If task execution fails
    """
    # Initialize task tracker
    tracker = TaskTracker(config.get("redis_url", "redis://localhost:6379/0"))
    
    try:
        logger.info(f"Starting bulk device operation: {task_id}")
        
        # Update status: Started
        tracker.update_task_status(task_id, "running", {
            "stage": "initialization", 
            "progress": 0,
            "started_at": datetime.utcnow().isoformat()
        })
        
        # Initialize NetBox client and orchestrator
        # NOTE: Async tasks run in separate worker processes and cannot share cache
        # with the main application singleton. Cache is disabled for async tasks.
        netbox_config = NetBoxConfig(
            url=config["netbox_url"],
            token=config["netbox_token"],
            timeout=config.get("timeout", 30),
            verify_ssl=config.get("verify_ssl", True)
        )
        # Disable cache for async tasks to prevent conflicts with main application cache
        netbox_config.cache.enabled = False
        
        netbox_client = NetBoxClient(netbox_config)
        logger.info(f"ASYNC TASK: NetBoxClient created with cache disabled (ID: {id(netbox_client)})")
        orchestrator = NetBoxBulkOrchestrator(netbox_client)
        batch_id = orchestrator.generate_batch_id()
        
        tracker.update_task_status(task_id, "running", {
            "stage": "initialization",
            "progress": 5,
            "batch_id": batch_id
        })
        
        # Process devices with progress tracking
        total_devices = len(devices_data)
        processed_devices = 0
        successful_devices = 0
        failed_devices = 0
        device_results = []
        
        tracker.update_task_status(task_id, "running", {
            "stage": "processing",
            "progress": 10,
            "total_devices": total_devices
        })
        
        for i, device_data in enumerate(devices_data):
            try:
                # Update progress every 10 devices
                if i % 10 == 0:
                    progress = 10 + (i / total_devices) * 80  # 10-90% for processing
                    tracker.update_task_status(task_id, "running", {
                        "stage": "processing",
                        "progress": progress,
                        "processed_devices": i,
                        "current_device": device_data.get("name", f"device_{i}")
                    })
                
                # Normalize and process device
                normalized_data = orchestrator.normalize_device_data(device_data)
                
                # Execute two-pass strategy
                pass_1_results = orchestrator.execute_pass_1(normalized_data, confirm=config.get("confirm", False))
                pass_2_results = orchestrator.execute_pass_2(normalized_data, pass_1_results, confirm=config.get("confirm", False))
                
                device_results.append({
                    "device_name": device_data.get("name"),
                    "status": "success",
                    "pass_1_results": pass_1_results,
                    "pass_2_results": pass_2_results
                })
                
                successful_devices += 1
                processed_devices += 1
                
                logger.debug(f"Successfully processed device: {device_data.get('name')}")
                
            except Exception as device_error:
                error_details = {
                    "device_name": device_data.get("name"),
                    "status": "failed",
                    "error": str(device_error),
                    "error_type": type(device_error).__name__
                }
                device_results.append(error_details)
                
                failed_devices += 1
                processed_devices += 1
                
                logger.error(f"Failed to process device {device_data.get('name')}: {device_error}")
        
        # Generate final results
        operation_report = orchestrator.generate_operation_report()
        
        final_results = {
            "status": "completed",
            "batch_id": batch_id,
            "summary": {
                "total_devices": total_devices,
                "processed_devices": processed_devices,
                "successful_devices": successful_devices,
                "failed_devices": failed_devices,
                "success_rate": round(successful_devices / total_devices * 100, 2) if total_devices > 0 else 100
            },
            "device_results": device_results,
            "operation_report": operation_report,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        # Update final status
        tracker.update_task_status(task_id, "completed", {
            "progress": 100,
            "results": final_results
        })
        
        logger.info(f"Bulk device operation completed: {task_id} ({successful_devices}/{total_devices} successful)")
        return final_results
        
    except Exception as e:
        error_info = {
            "error": str(e),
            "error_type": type(e).__name__,
            "failed_at": datetime.utcnow().isoformat(),
            "processed_devices": processed_devices if 'processed_devices' in locals() else 0
        }
        
        tracker.update_task_status(task_id, "failed", error_info)
        logger.error(f"Bulk device operation failed: {task_id} - {e}")
        raise TaskError(f"Bulk device operation failed: {e}")


# Initialize global task manager (will be configured in server.py)
task_manager: Optional[AsyncTaskManager] = None


def initialize_task_manager(redis_url: str = "redis://localhost:6379/0") -> AsyncTaskManager:
    """
    Initialize global task manager instance.
    
    Args:
        redis_url: Redis connection URL
        
    Returns:
        Configured AsyncTaskManager instance
    """
    global task_manager
    
    if not RQ_AVAILABLE:
        logger.warning("Redis Queue (RQ) not available - async operations disabled")
        return None
    
    try:
        task_manager = AsyncTaskManager(redis_url)
        logger.info("Async task manager initialized successfully")
        return task_manager
    except Exception as e:
        logger.error(f"Failed to initialize task manager: {e}")
        return None


def get_task_manager() -> Optional[AsyncTaskManager]:
    """Get the global task manager instance."""
    return task_manager