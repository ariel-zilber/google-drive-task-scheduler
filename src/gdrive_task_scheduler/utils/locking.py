# utils/locking.py

import os
import random
import time
from filelock import FileLock, Timeout


class LockAcquisitionError(Exception):
    """Custom exception for lock acquisition failures."""
    pass


def acquire_lock(lock_dir: str, name: str, timeout: float = 10, max_retries: int = 5) -> FileLock:
    """
    Acquire a file-based lock with exponential backoff retry logic.

    Args:
        lock_dir (str): Directory where lock files are stored.
        name (str): Logical name of the lock (used for filename).
        timeout (float): Timeout in seconds for acquiring each attempt.
        max_retries (int): Maximum number of retry attempts.

    Returns:
        FileLock: An acquired lock object (must be released manually).

    Raises:
        LockAcquisitionError: If the lock could not be acquired after retries.
    """
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, f"{name}.lock")

    for attempt in range(max_retries):
        try:
            lock = FileLock(lock_path, timeout=timeout)
            lock.acquire()
            return lock
        except Timeout:
            if attempt < max_retries - 1:
                backoff = 0.1 * (2 ** attempt) * (1 + random.random())
                time.sleep(min(backoff, 5.0))  # cap at 5 seconds
            else:
                raise LockAcquisitionError(f"Failed to acquire lock: {name}")

    raise LockAcquisitionError(f"Failed to acquire lock: {name} after {max_retries} attempts")


def try_release_lock(lock: FileLock) -> None:
    """Safely release a lock object."""
    try:
        if lock.is_locked:
            lock.release()
    except Exception:
        pass
