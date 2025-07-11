# google-drive-task-scheduler

A lightweight, file-based task scheduler designed to run on **Google Colab** using **Google Drive** as a shared backend. It enables distributed and concurrent task execution across multiple notebook instances by tracking task state via file extensions (`.todo.yaml`, `.running.yaml`, `.done.yaml`).

## Features

- 🧠 Simple file-based design — no need for databases or message queues.
- 📂 Shared-state coordination using Google Drive.
- 🚀 Safe for concurrent execution across multiple Colab tabs or users.
- 📊 Supports custom task formats (YAML/JSON).
- 🔄 Easily extendable with retries, priorities, or heartbeats.

## Use Case

Ideal for:
- Parameter sweeps and ML experiments
- Parallel data processing tasks
- Lightweight meta-agent task routing
- Educational/distributed execution on free compute (e.g. Colab)

## Directory Structure

```text
gdrive_task_scheduler/
├── scheduler.py            # High-level scheduler logic and lifecycle
├── task_manager.py         # Task creation, transitions, and state
├── heartbeat.py            # Heartbeat loop and status tracking
├── recovery.py             # Stale task detection & recovery
├── utils/
│   ├── file_ops.py         # Atomic rename, safe file writes, cleanup
│   ├── locking.py          # File locking and retry logic
│   └── process_utils.py    # Process and memory checking
├── models/
│   └── task.py             # Task representation (optional dataclass)
