#!/usr/bin/env python3
"""
NetBox MCP RQ Worker

Background worker process for executing long-running NetBox operations.
Handles bulk device operations, synchronization tasks, and other async work.
"""

import os
import sys
import logging
from typing import Optional

try:
    from rq import Worker, Connection
    from redis import Redis
    RQ_AVAILABLE = True
except ImportError:
    import logging
    logging.error("Redis Queue (RQ) not available. Install with: pip install rq redis")
    sys.exit(1)

from .config import load_config
from .tasks import initialize_task_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_worker(redis_url: str = None, queue_names: list = None) -> Worker:
    """
    Create and configure RQ worker.
    
    Args:
        redis_url: Redis connection URL
        queue_names: List of queue names to process
        
    Returns:
        Configured RQ Worker instance
    """
    if redis_url is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    if queue_names is None:
        queue_names = ["netbox_bulk", "default"]
    
    # Create Redis connection
    redis_conn = Redis.from_url(redis_url)
    
    # Test connection
    try:
        redis_conn.ping()
        logger.info(f"Connected to Redis: {redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    
    # Create worker
    worker = Worker(queue_names, connection=redis_conn)
    
    logger.info(f"Worker created for queues: {queue_names}")
    return worker


def run_worker():
    """Main worker entry point."""
    try:
        logger.info("Starting NetBox MCP Worker...")
        
        # Load configuration
        try:
            config = load_config()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
        
        # Initialize task manager
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        task_manager = initialize_task_manager(redis_url)
        
        if task_manager is None:
            logger.error("Failed to initialize task manager")
            sys.exit(1)
        
        # Create and start worker
        worker = create_worker(redis_url)
        
        logger.info("Worker ready - waiting for tasks...")
        logger.info("Press Ctrl+C to stop")
        
        # Start worker loop
        worker.work(with_scheduler=True)
        
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


def worker_health_check() -> bool:
    """
    Check if worker can connect to Redis and process basic tasks.
    
    Returns:
        True if worker is healthy, False otherwise
    """
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_conn = Redis.from_url(redis_url)
        
        # Test basic Redis operations
        redis_conn.ping()
        redis_conn.set("worker_health_check", "ok", ex=10)
        result = redis_conn.get("worker_health_check")
        
        return result == b"ok"
    except Exception as e:
        logger.error(f"Worker health check failed: {e}")
        return False


if __name__ == "__main__":
    run_worker()