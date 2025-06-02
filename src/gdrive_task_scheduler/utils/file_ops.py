# utils/file_ops.py

import os
import shutil
import yaml
import time
from datetime import datetime


def atomic_write_yaml(path: str, data: dict) -> None:
    """Write YAML atomically to avoid partial writes."""
    temp_path = f"{path}.tmp"
    with open(temp_path, 'w') as f:
        yaml.dump(data, f)
    safe_rename(temp_path, path)


def atomic_read_yaml(path: str) -> dict:
    """Safely read a YAML file."""
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def safe_rename(src: str, dst: str) -> None:
    """Atomic rename with fallbacks to handle cross-device renames."""
    try:
        os.rename(src, dst)
    except OSError:
        try:
            shutil.move(src, dst)
        except Exception:
            # Last resort: copy then delete
            try:
                shutil.copy2(src, dst)
                os.remove(src)
            except Exception:
                pass


def cleanup_temp_files(dir_path: str, older_than_secs: int = 3600) -> None:
    """Remove temporary or hidden task files older than a given age."""
    if not os.path.exists(dir_path):
        return

    try:
        for filename in os.listdir(dir_path):
            if not filename.startswith('.'):
                continue

            full_path = os.path.join(dir_path, filename)
            try:
                age = time.time() - os.path.getmtime(full_path)
                if age > older_than_secs and filename.endswith(('.reserved', '.completing', '.recovering', '.tmp')):
                    os.remove(full_path)
            except Exception:
                pass
    except Exception:
        pass


def get_yaml_files(dir_path: str) -> list:
    """Return list of visible .yaml files in a directory."""
    if not os.path.exists(dir_path):
        return []
    return [
        f for f in os.listdir(dir_path)
        if f.endswith('.yaml') and not f.startswith('.')
    ]


def timestamped_filename(base_name: str, ext: str = ".yaml") -> str:
    """Generate a unique timestamped filename."""
    return f"{base_name}_{int(time.time())}{ext}"


def touch_file(path: str) -> None:
    """Update file modification time or create the file if it doesn't exist."""
    with open(path, 'a'):
        os.utime(path, None)


def file_is_fresh(path: str, max_age_seconds: int) -> bool:
    """Check if the file has been modified within a time window."""
    try:
        mtime = os.path.getmtime(path)
        return (time.time() - mtime) <= max_age_seconds
    except Exception:
        return False


def try_remove(path: str) -> None:
    """Attempt to remove a file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
