"""netbox_mcp.debug_monitor

This project (netbox-mcp 1.1.3  ) references a `debug_monitor` module from `server.py`,
but the upstream repository does not ship it. This module provides lightweight,
dependency-free debug instrumentation.

Design goals:
- Zero required configuration (safe defaults).
- Optional opt-in verbose protocol/tool logging via env var.
- Never raise exceptions from logging helpers (best-effort only).
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger("netbox_mcp.debug_monitor")

def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}

def _safe(obj: Any) -> Any:
    """Best-effort JSON-safe conversion."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        try:
            return str(obj)
        except Exception:
            return "<unprintable>"

def _json_line(record: Dict[str, Any]) -> str:
    try:
        return json.dumps(record, ensure_ascii=False, default=_safe)
    except Exception:
        # Absolute last resort
        return json.dumps({"ts": record.get("ts"), "event": record.get("event"), "note": "serialization_failed"})

@dataclass
class DebugMonitor:
    enabled: bool = field(default_factory=lambda: _truthy(os.getenv("NETBOX_MCP_DEBUG_MONITOR")))
    log_path: Optional[str] = field(default_factory=lambda: os.getenv("NETBOX_MCP_DEBUG_LOG_PATH") or None)
    include_payloads: bool = field(default_factory=lambda: _truthy(os.getenv("NETBOX_MCP_DEBUG_INCLUDE_PAYLOADS")))

    def _emit(self, level: int, event: str, payload: Dict[str, Any]) -> None:
        record: Dict[str, Any] = {
            "ts": time.time(),
            "event": event,
            **{k: _safe(v) for k, v in (payload or {}).items()},
        }

        # 1) Standard logging (always)
        try:
            msg = _json_line(record)
            _LOGGER.log(level, msg)
        except Exception:
            # Never break server execution
            pass

        # 2) Optional JSONL file sink
        if self.log_path:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(_json_line(record) + "\n")
            except Exception:
                pass

_MONITOR: Optional[DebugMonitor] = None

def get_monitor() -> DebugMonitor:
    global _MONITOR
    if _MONITOR is None:
        _MONITOR = DebugMonitor()
        # If someone didn't configure logging, make sure there's at least a basic handler.
        # (No-op if already configured elsewhere.)
        try:
            logging.basicConfig(level=logging.INFO)
        except Exception:
            pass
    return _MONITOR

# ---- Public helper functions used by server.py ----

def log_startup(message: str, extra: Optional[Dict[str, Any]] = None) -> None:
    monitor = get_monitor()
    monitor._emit(logging.INFO, "startup", {"message": message, **(extra or {})})

def log_protocol_message(direction: str, payload: Any) -> None:
    monitor = get_monitor()
    if not monitor.enabled:
        return
    # Some payloads can be large; allow opt-out by default
    data = payload if monitor.include_payloads else {"summary": "payload_hidden", "type": type(payload).__name__}
    monitor._emit(logging.DEBUG, "protocol", {"direction": direction, "payload": data})

def log_connection_event(event: str, details: Any = None) -> None:
    monitor = get_monitor()
    if not monitor.enabled:
        return
    monitor._emit(logging.INFO, "connection", {"name": event, "details": details})

def log_tool_call(tool_name: str, args: Any = None) -> None:
    monitor = get_monitor()
    if not monitor.enabled:
        return
    data = args if monitor.include_payloads else {"summary": "args_hidden", "type": type(args).__name__}
    monitor._emit(logging.INFO, "tool_call", {"tool": tool_name, "args": data})

def log_performance(metric: str, value: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
    monitor = get_monitor()
    if not monitor.enabled:
        return
    payload: Dict[str, Any] = {"metric": metric, "value": value}
    if extra:
        payload.update(extra)
    monitor._emit(logging.DEBUG, "performance", payload)

def log_error(message: str, exc: Optional[BaseException] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    monitor = get_monitor()
    tb = None
    if exc is not None:
        try:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        except Exception:
            tb = "<traceback_unavailable>"
    monitor._emit(logging.ERROR, "error", {"message": message, "exception": str(exc) if exc else None, "traceback": tb, **(extra or {})})
