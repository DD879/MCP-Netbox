#!/usr/bin/env python3
"""
🧠 ULTRATHINK LIVE MONITOR

Real-time monitoring script to watch NetBox MCP server debug logs while Claude Desktop connects.
Run this in a separate terminal while testing Claude Desktop connections.
"""

import time
import subprocess
import json
from pathlib import Path
import threading
import sys

class LiveMonitor:
    def __init__(self):
        self.debug_log_path = Path("/tmp/netbox-mcp-ultrathink-debug.log")
        self.protocol_log_path = Path("/tmp/netbox-mcp-protocol.jsonl")
        self.running = True

    def monitor_debug_log(self):
        """Monitor the debug log file for real-time updates."""
        print("🧠 MONITORING DEBUG LOG...")

        try:
            # Use tail to follow the log file
            cmd = ["tail", "-f", str(self.debug_log_path)]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            while self.running:
                line = process.stdout.readline()
                if line:
                    print(f"🔍 DEBUG: {line.strip()}")
                else:
                    time.sleep(0.1)

        except FileNotFoundError:
            print(f"⚠️  Debug log not found: {self.debug_log_path}")
            print("Start the NetBox MCP server first!")
        except Exception as e:
            print(f"❌ Error monitoring debug log: {e}")

    def monitor_protocol_log(self):
        """Monitor the JSON protocol log for MCP interactions."""
        print("🧠 MONITORING PROTOCOL LOG...")

        last_size = 0

        while self.running:
            try:
                if self.protocol_log_path.exists():
                    current_size = self.protocol_log_path.stat().st_size
                    if current_size > last_size:
                        with open(self.protocol_log_path, 'r') as f:
                            f.seek(last_size)
                            new_lines = f.read()

                        for line in new_lines.strip().split('\n'):
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    self.display_protocol_message(data)
                                except json.JSONDecodeError:
                                    pass

                        last_size = current_size

                time.sleep(0.2)

            except Exception as e:
                print(f"❌ Error monitoring protocol log: {e}")
                time.sleep(1)

    def display_protocol_message(self, data):
        """Display formatted protocol message."""
        timestamp = data.get('timestamp', '')[:19]  # Truncate microseconds
        direction = data.get('direction', 'UNKNOWN')
        interaction_id = data.get('interaction_id', 0)
        message = data.get('message', {})

        if direction == "RECEIVED":
            method = message.get('method', 'unknown')
            print(f"📨 {timestamp} #{interaction_id:03d} Claude Desktop → Server: {method}")

            if method == 'initialize':
                client_info = message.get('params', {}).get('clientInfo', {})
                print(f"   🤝 Client: {client_info.get('name', 'unknown')} v{client_info.get('version', 'unknown')}")

            elif method == 'tools/call':
                tool_name = message.get('params', {}).get('name', 'unknown')
                print(f"   🔧 Tool: {tool_name}")

        else:
            print(f"📤 {timestamp} #{interaction_id:03d} Server → Claude Desktop: Response")

    def run(self):
        """Run the live monitor."""
        print("🧠 ULTRATHINK LIVE MONITOR STARTING...")
        print("=" * 80)
        print("This will show real-time NetBox MCP server activity.")
        print("Start Claude Desktop now and try to use NetBox tools!")
        print("Press Ctrl+C to stop monitoring.")
        print("=" * 80)

        # Clear any existing logs
        for log_path in [self.debug_log_path, self.protocol_log_path]:
            if log_path.exists():
                log_path.unlink()

        # Start monitoring threads
        debug_thread = threading.Thread(target=self.monitor_debug_log)
        protocol_thread = threading.Thread(target=self.monitor_protocol_log)

        debug_thread.daemon = True
        protocol_thread.daemon = True

        debug_thread.start()
        protocol_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 STOPPING MONITOR...")
            self.running = False

if __name__ == "__main__":
    monitor = LiveMonitor()
    monitor.run()