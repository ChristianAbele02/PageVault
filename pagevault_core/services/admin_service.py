from __future__ import annotations

import shutil
from pathlib import Path


def tail_log(path: str, lines: int = 200) -> list[str]:
    log_path = Path(path)
    if not log_path.exists() or not log_path.is_file():
        return []

    # Read as UTF-8 but replace undecodable bytes to avoid admin-page crashes.
    content = log_path.read_text(encoding="utf-8", errors="replace")
    all_lines = content.splitlines()
    return all_lines[-max(1, min(lines, 2000)) :]


def storage_diagnostics(database_path: str) -> dict[str, int | str]:
    db_path = Path(database_path)
    data_dir = db_path.parent if db_path.parent.exists() else Path(".")
    usage = shutil.disk_usage(data_dir)
    return {
        "database_path": str(db_path),
        "database_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
    }
