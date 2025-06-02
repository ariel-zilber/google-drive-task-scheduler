# recovery.py

import os
import time
import yaml
from datetime import datetime, timedelta
from typing import Set

from utils.file_ops import (
    atomic_write_yaml, safe_rename, get_yaml_files
)
from utils.locking import acquire_lock, try_release_lock
from utils.process_utils import is_process_running


class TaskRecovery:
    """
    Handles recovery of stale or orphaned tasks from the in_progress directory.
    """

    def __init__(self, in_progress_dir: str, todo_dir: str, lock_dir: str,
                 status_dir: str, corrupted_dir: str, timeout_minutes: int = 15):
        self.in_progress_dir = in_progress_dir
        self.todo_dir = todo_dir
        self.lock_dir = lock_dir
        self.status_dir = status_dir
        self.corrupted_dir = corrupted_dir
        self.timeout = timedelta(minutes=timeout_minutes)

    def recover_stale_tasks(self, current_session_id: str, current_hostname: str) -> int:
        """
        Attempt to recover stale tasks from in_progress directory.

        Returns:
            int: Number of tasks recovered.
        """
        recovered_count = 0
        active_sessions = self._get_active_sessions()

        try:
            with acquire_lock(self.lock_dir, "stale_check", timeout=10):
                if not os.path.exists(self.in_progress_dir):
                    return 0

                for filename in get_yaml_files(self.in_progress_dir):
                    task_path = os.path.join(self.in_progress_dir, filename)

                    try:
                        with open(task_path, 'r') as f:
                            task_data = yaml.safe_load(f)

                        session_id = task_data.get('session_id')
                        pid = task_data.get('process_id')
                        host = task_data.get('host')
                        started_str = task_data.get('started_at')

                        # Determine if task is stale
                        stale = False
                        if session_id and session_id not in active_sessions:
                            stale = True
                        elif pid and not is_process_running(pid, host):
                            stale = True
                        elif started_str:
                            try:
                                started = datetime.fromisoformat(started_str)
                                if datetime.now() - started > self.timeout:
                                    stale = True
                            except Exception:
                                stale = True
                        else:
                            stale = True

                        if stale:
                            recovering_path = os.path.join(self.in_progress_dir, f".{filename}.recovering")
                            safe_rename(task_path, recovering_path)

                            task_data.update({
                                'retries': task_data.get('retries', 0) + 1,
                                'last_failed': datetime.now().isoformat(),
                                'failure_reason': "Stale task recovery",
                                'recovered_by': os.getpid()
                            })

                            new_path = os.path.join(self.todo_dir, filename)
                            atomic_write_yaml(f"{new_path}.tmp", task_data)
                            safe_rename(f"{new_path}.tmp", new_path)

                            try:
                                os.remove(recovering_path)
                            except Exception:
                                pass

                            recovered_count += 1
                    except Exception as e:
                        print(f"[Recovery] Failed to recover {filename}: {e}")
        except Exception as e:
            print(f"[Recovery] Lock acquisition failed: {e}")

        return recovered_count

    def _get_active_sessions(self) -> Set[str]:
        """
        Reads heartbeat files to determine active session IDs.

        Returns:
            Set[str]: Set of session IDs still considered active.
        """
        active = set()
        now = datetime.now()

        if not os.path.exists(self.status_dir):
            return active

        try:
            for file in os.listdir(self.status_dir):
                if not file.endswith(".heartbeat"):
                    continue

                path = os.path.join(self.status_dir, file)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if now - mtime > self.timeout:
                        continue

                    with open(path, 'r') as f:
                        data = yaml.safe_load(f)

                    beat_time_str = data.get('last_beat')
                    if not beat_time_str:
                        continue

                    beat_time = datetime.fromisoformat(beat_time_str)
                    if now - beat_time <= self.timeout:
                        active.add(data.get('session_id'))
                except Exception:
                    continue
        except Exception:
            pass

        return active
