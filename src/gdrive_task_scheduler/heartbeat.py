# heartbeat.py

import os
import threading
import time
import yaml
from datetime import datetime
from utils.file_ops import atomic_write_yaml
from utils.process_utils import current_hostname


class Heartbeat:
    """
    Maintains a heartbeat file to indicate that a scheduler process is alive.
    """

    def __init__(self, session_id: str, process_id: int, status_dir: str,
                 interval: int = 30, start_time: datetime = None, hostname: str = None):
        self.session_id = session_id
        self.process_id = process_id
        self.status_dir = status_dir
        self.interval = interval
        self.start_time = start_time or datetime.now()
        self.hostname = hostname or current_hostname()
        self._shutdown = False
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)

    def start(self):
        """Start the heartbeat loop in a background thread."""
        os.makedirs(self.status_dir, exist_ok=True)
        self._shutdown = False
        self._thread.start()

    def stop(self):
        """Stop the heartbeat loop."""
        self._shutdown = True
        self._thread.join(timeout=5)

    def _heartbeat_loop(self):
        while not self._shutdown:
            try:
                self._write_heartbeat()
                time.sleep(self.interval)
            except Exception as e:
                if not self._shutdown:
                    print(f"[Heartbeat] Error: {e}")
                time.sleep(5)

    def _write_heartbeat(self):
        """Write heartbeat YAML file with session/process metadata."""
        heartbeat_file = os.path.join(self.status_dir, f"{self.session_id}.heartbeat")
        data = {
            'session_id': self.session_id,
            'process_id': self.process_id,
            'hostname': self.hostname,
            'last_beat': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds()
        }
        atomic_write_yaml(heartbeat_file, data)
