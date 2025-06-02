# task_manager.py

import os
import uuid
import time
import yaml
from datetime import datetime
from typing import Optional, Dict, Any, List

from task import Task
from utils.locking import acquire_lock
from utils.file_ops import atomic_write_yaml, get_yaml_files, try_remove


class TaskManager:
    """
    Handles task creation, listing, and per-process task ownership logic.
    """

    def __init__(self,
                 todo_dir: str,
                 in_progress_dir: str,
                 done_dir: str,
                 corrupted_dir: str,
                 lock_dir: str,
                 process_id: int,
                 session_id: str):
        self.todo_dir = todo_dir
        self.in_progress_dir = in_progress_dir
        self.done_dir = done_dir
        self.corrupted_dir = corrupted_dir
        self.lock_dir = lock_dir
        self.process_id = process_id
        self.session_id = session_id

    def create_task(self, task_data: Dict[str, Any], task_id: Optional[str] = None) -> Optional[str]:
        """
        Create a new task file in the todo directory.

        Args:
            task_data (Dict[str, Any]): Task contents.
            task_id (str, optional): Filename (without .yaml) or None for auto.

        Returns:
            str: Final task filename or None on failure.
        """
        if task_id is None:
            task_id = f"task_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        if not task_id.endswith(".yaml"):
            task_id += ".yaml"

        task_path = os.path.join(self.todo_dir, task_id)

        task_data = task_data.copy()
        task_data.update({
            "created_at": datetime.now().isoformat(),
            "created_by": self.process_id,
            "retries": 0,
            "session_id": self.session_id
        })

        try:
            with acquire_lock(self.lock_dir, "task_create", timeout=10, max_retries=3):
                atomic_write_yaml(f"{task_path}.tmp", task_data)
                os.rename(f"{task_path}.tmp", task_path)
                print(f"[TaskManager] Created task: {task_id}")
                return task_id
        except Exception as e:
            print(f"[TaskManager] Failed to create task {task_id}: {e}")
            try_remove(f"{task_path}.tmp")
            return None

    def count_tasks(self) -> Dict[str, int]:
        """
        Count tasks in each directory.

        Returns:
            Dict[str, int]: Counts for todo, in_progress, done, corrupted.
        """
        counts = {"todo": 0, "in_progress": 0, "done": 0, "corrupted": 0}

        try:
            counts["todo"] = len(get_yaml_files(self.todo_dir))
        except Exception:
            pass

        try:
            counts["in_progress"] = len(get_yaml_files(self.in_progress_dir))
        except Exception:
            pass

        try:
            counts["done"] = len(get_yaml_files(self.done_dir))
        except Exception:
            pass

        try:
            counts["corrupted"] = len(os.listdir(self.corrupted_dir))
        except Exception:
            pass

        return counts

    def list_owned_in_progress_tasks(self) -> List[Task]:
        """
        Return a list of tasks currently owned by this process.

        Returns:
            List[Task]: Owned in-progress tasks.
        """
        owned = []
        if not os.path.exists(self.in_progress_dir):
            return owned

        for fname in get_yaml_files(self.in_progress_dir):
            path = os.path.join(self.in_progress_dir, fname)
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
                if (data.get("process_id") == self.process_id and
                        data.get("session_id") == self.session_id):
                    owned.append(Task(filename=fname, data=data, path=path))
            except Exception:
                continue
        return owned

    def count_tasks_by_process(self) -> Dict[int, int]:
        """
        Count number of in-progress tasks per process.

        Returns:
            Dict[int, int]: Mapping from PID to task count.
        """
        counts = {}
        for fname in get_yaml_files(self.in_progress_dir):
            path = os.path.join(self.in_progress_dir, fname)
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
                pid = data.get("process_id")
                if pid is not None:
                    counts[pid] = counts.get(pid, 0) + 1
            except Exception:
                continue
        return counts
