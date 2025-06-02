# scheduler.py

import os
import uuid
import signal
from datetime import datetime

from task import Task
from heartbeat import Heartbeat
from recovery import TaskRecovery
from utils.locking import acquire_lock
from utils.process_utils import (
    is_process_running,
    get_memory_usage_mb,
    get_process_uptime,
    current_hostname
)
from utils.file_ops import (
    get_yaml_files,
    atomic_write_yaml,
    safe_rename,
    cleanup_temp_files,
    try_remove
)


class TaskScheduler:
    def __init__(self, base_dir=".", timeout_minutes=15, heartbeat_interval=30):
        self.session_id = str(uuid.uuid4())
        self.process_id = os.getpid()
        self.hostname = current_hostname()
        self.start_time = datetime.now()
        self.base_dir = os.path.abspath(base_dir)
        self.timeout_minutes = timeout_minutes
        self.heartbeat_interval = heartbeat_interval
        self._shutdown = False

        # Directory setup
        self.todo_dir = os.path.join(self.base_dir, "todo")
        self.in_progress_dir = os.path.join(self.base_dir, "in_progress")
        self.done_dir = os.path.join(self.base_dir, "done")
        self.corrupted_dir = os.path.join(self.base_dir, "corrupted")
        self.status_dir = os.path.join(self.base_dir, ".status")
        self.lock_dir = os.path.join(self.base_dir, ".locks")

        for d in [
            self.todo_dir, self.in_progress_dir, self.done_dir,
            self.corrupted_dir, self.status_dir, self.lock_dir
        ]:
            os.makedirs(d, exist_ok=True)

        # Setup modules
        self.heartbeat = Heartbeat(
            session_id=self.session_id,
            process_id=self.process_id,
            status_dir=self.status_dir,
            interval=self.heartbeat_interval,
            start_time=self.start_time,
            hostname=self.hostname
        )
        self.recovery = TaskRecovery(
            in_progress_dir=self.in_progress_dir,
            todo_dir=self.todo_dir,
            lock_dir=self.lock_dir,
            status_dir=self.status_dir,
            corrupted_dir=self.corrupted_dir,
            timeout_minutes=self.timeout_minutes
        )

        # Signal handling
        try:
            signal.signal(signal.SIGTERM, self._handle_shutdown)
            signal.signal(signal.SIGINT, self._handle_shutdown)
        except ValueError:
            pass

        self.heartbeat.start()

    def _handle_shutdown(self, signum, frame):
        print(f"[PID {self.process_id}] Shutting down due to signal {signum}")
        self._shutdown = True
        self.heartbeat.stop()
        self._cleanup_status_files()
        exit(128 + signum)

    def _cleanup_status_files(self):
        try_remove(os.path.join(self.status_dir, f"{self.process_id}.status"))
        try_remove(os.path.join(self.status_dir, f"{self.session_id}.heartbeat"))

    def get_next_task(self, check_stale=True):
        if self._shutdown:
            return None

        cleanup_temp_files(self.todo_dir)
        if check_stale:
            self.recovery.recover_stale_tasks(self.session_id, self.hostname)

        try:
            with acquire_lock(self.lock_dir, "todo_lock", timeout=5):
                tasks = get_yaml_files(self.todo_dir)
                if not tasks:
                    return None

                # Pick highest priority or random among top
                tasks.sort(key=lambda f: self._get_task_priority(f), reverse=True)
                task_file = tasks[0]  # You can add randomness among top-k
                task_path = os.path.join(self.todo_dir, task_file)
                return Task.from_file(task_path)
        except Exception as e:
            print(f"[Scheduler] Failed to get next task: {e}")
            return None

    def _get_task_priority(self, filename):
        try:
            with open(os.path.join(self.todo_dir, filename), 'r') as f:
                data = yaml.safe_load(f)
            return data.get("priority", 0)
        except Exception:
            return 0

    def move_to_in_progress(self, task: Task) -> Task:
        """Reserve task and move it to in_progress."""
        if self._shutdown or not task:
            return None

        temp_reserved = os.path.join(self.todo_dir, f".{task.filename}.reserved")
        dst_path = os.path.join(self.in_progress_dir, task.filename)

        try:
            with acquire_lock(self.lock_dir, "task_move", timeout=10):
                if not os.path.exists(task.path):
                    return None

                safe_rename(task.path, temp_reserved)

                task.mark_started(self.process_id, self.hostname, self.session_id)
                temp_dst = f"{dst_path}.tmp"
                atomic_write_yaml(temp_dst, task.data)
                safe_rename(temp_dst, dst_path)

                try_remove(temp_reserved)
                task.path = dst_path
                return task
        except Exception as e:
            print(f"[Scheduler] Move to in_progress failed: {e}")
            safe_rename(temp_reserved, task.path)
            return None

    def move_to_done(self, task: Task, success=True, results=None, error=None) -> bool:
        if not task or self._shutdown:
            return False

        in_prog = task.path
        completing = os.path.join(self.in_progress_dir, f".{task.filename}.completing")
        done_path = os.path.join(self.done_dir, task.filename)

        try:
            with acquire_lock(self.lock_dir, "task_done", timeout=10):
                safe_rename(in_prog, completing)
                task.mark_completed(success=success, results=results, error=error)
                temp_done = f"{done_path}.tmp"
                atomic_write_yaml(temp_done, task.data)
                safe_rename(temp_done, done_path)
                try_remove(completing)
                return True
        except Exception as e:
            print(f"[Scheduler] Move to done failed: {e}")
            safe_rename(completing, in_prog)
            return False

    def report_progress(self, task: Task, pct: float = None, msg: str = None) -> bool:
        """Update task progress (percentage and/or message)."""
        if not task or self._shutdown:
            return False

        try:
            with acquire_lock(self.lock_dir, f"progress_{task.filename}", timeout=5):
                with open(task.path, 'r') as f:
                    task_data = yaml.safe_load(f)

                task_data.setdefault('progress', {})
                if pct is not None:
                    task_data['progress']['percentage'] = max(0, min(100, pct))
                if msg:
                    task_data['progress']['status'] = str(msg)
                task_data['progress']['updated_at'] = datetime.now().isoformat()

                atomic_write_yaml(f"{task.path}.tmp", task_data)
                safe_rename(f"{task.path}.tmp", task.path)
                return True
        except Exception as e:
            print(f"[Scheduler] Failed to update progress: {e}")
            return False

    def close(self):
        self._shutdown = True
        self.heartbeat.stop()
        self._cleanup_status_files()

    def __del__(self):
        self.close()
