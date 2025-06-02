# utils/process_utils.py

import os
import socket
from datetime import datetime


def is_process_running(pid: int, hostname: str = None) -> bool:
    """
    Check whether the process with the given PID is running on this host.

    Args:
        pid (int): Process ID.
        hostname (str, optional): Hostname to compare.

    Returns:
        bool: True if the process is running on the expected host, False otherwise.
    """
    if hostname and hostname != socket.gethostname():
        return False

    try:
        pid = int(pid)
        if pid <= 0:
            return False

        # Check /proc/<pid> existence (Linux only)
        if os.path.exists(f"/proc/{pid}"):
            return True

        # Fallback signal check
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, PermissionError, OSError):
        return False
    except Exception:
        return False


def get_memory_usage_mb(pid: int) -> int:
    """
    Get the memory usage (RSS) of a process in megabytes.

    Args:
        pid (int): Process ID.

    Returns:
        int: Memory usage in MB, or 0 on error.
    """
    try:
        status_path = f"/proc/{pid}/status"
        if os.path.exists(status_path):
            with open(status_path, 'r') as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        return int(parts[1]) // 1024  # Convert KB to MB
    except Exception:
        pass
    return 0


def get_process_uptime(pid: int) -> float:
    """
    Get the uptime of a process in seconds.

    Args:
        pid (int): Process ID.

    Returns:
        float: Uptime in seconds, or 0.0 on failure.
    """
    try:
        stat_path = f"/proc/{pid}/stat"
        if os.path.exists(stat_path):
            with open(stat_path, 'r') as f:
                parts = f.read().split()
                start_ticks = int(parts[21])

                clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                with open('/proc/uptime', 'r') as f2:
                    system_uptime = float(f2.read().split()[0])

                process_uptime = system_uptime - (start_ticks / clk_tck)
                return max(0.0, process_uptime)
    except Exception:
        pass
    return 0.0


def current_hostname() -> str:
    """Return the current machine's hostname."""
    return socket.gethostname()
