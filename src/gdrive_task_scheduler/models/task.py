# task.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import yaml
import os


@dataclass
class Task:
    """Represents a single task in the scheduler."""
    filename: str
    data: Dict[str, Any]
    path: str
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_file(cls, path: str):
        """Load task from a YAML file."""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            filename = os.path.basename(path)
            return cls(filename=filename, data=data, path=path)
        except Exception as e:
            raise RuntimeError(f"Failed to load task from {path}: {e}")

    def save(self, directory: str, suffix: str = ""):
        """Save task data to a YAML file in a given directory."""
        target_filename = self.filename
        if suffix:
            target_filename = f"{os.path.splitext(self.filename)[0]}{suffix}.yaml"
        target_path = os.path.join(directory, target_filename)

        temp_path = f"{target_path}.tmp"
        try:
            with open(temp_path, 'w') as f:
                yaml.dump(self.data, f)
            os.replace(temp_path, target_path)
            self.path = target_path
        except Exception as e:
            raise RuntimeError(f"Failed to save task to {target_path}: {e}")

    def update(self, updates: Dict[str, Any]):
        """Update task data in-place."""
        self.data.update(updates)

    def get_priority(self, default: int = 0) -> int:
        return self.data.get('priority', default)

    def is_owned_by(self, process_id: int, session_id: str) -> bool:
        return (self.data.get('process_id') == process_id and 
                self.data.get('session_id') == session_id)

    def mark_failed(self, reason: str):
        self.data['retries'] = self.data.get('retries', 0) + 1
        self.data['last_failed'] = datetime.now().isoformat()
        self.data['failure_reason'] = reason

    def mark_started(self, process_id: int, hostname: str, session_id: str):
        self.data['started_at'] = datetime.now().isoformat()
        self.data['process_id'] = process_id
        self.data['host'] = hostname
        self.data['session_id'] = session_id

    def mark_completed(self, success: bool, results: Optional[Any] = None, error: Optional[str] = None):
        self.data['completed_at'] = datetime.now().isoformat()
        self.data['success'] = success
        self.data['results'] = results
        self.data['error'] = error

        try:
            start = datetime.fromisoformat(self.data.get('started_at'))
            self.data['duration_seconds'] = (datetime.now() - start).total_seconds()
        except Exception:
            self.data['duration_seconds'] = 0
