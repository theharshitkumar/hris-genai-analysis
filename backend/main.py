from __future__ import annotations

import csv
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.app_config import configs


@dataclass
class DatabaseStatus:
    db_exists: bool
    table_exists: bool
    db_row_count: Optional[int]
    csv_row_count: Optional[int]
    message: str


def count_csv_rows(csv_path: Path) -> int:
    with csv_path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        # Skip header
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def get_database_status() -> DatabaseStatus:
    db_path = Path(configs.DB_PATH)
    csv_path = Path(configs.CSV_PATH)

    db_exists = db_path.exists()
    csv_rows: Optional[int] = None
    if csv_path.exists():
        try:
            csv_rows = count_csv_rows(csv_path)
        except Exception:
            csv_rows = None

    if not db_exists:
        return DatabaseStatus(
            db_exists=False,
            table_exists=False,
            db_row_count=None,
            csv_row_count=csv_rows,
            message=f'Database not found at {db_path}',
        )

    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            tbl = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='employees'"
            ).fetchone()
            table_exists = tbl is not None

            row_count: Optional[int] = None
            if table_exists:
                row_count = cur.execute('SELECT COUNT(*) FROM employees').fetchone()[0]
    except sqlite3.Error as e:
        return DatabaseStatus(
            db_exists=True,
            table_exists=False,
            db_row_count=None,
            csv_row_count=csv_rows,
            message=f'Error opening database: {e}',
        )

    msg_parts = [f'DB: {db_path}']
    if table_exists:
        msg_parts.append(f'employees rows: {row_count}')
    else:
        msg_parts.append('employees table: MISSING')
    if csv_rows is not None:
        msg_parts.append(f'CSV rows: {csv_rows}')

    message = ' | '.join(msg_parts)

    return DatabaseStatus(
        db_exists=True,
        table_exists=table_exists,
        db_row_count=row_count if table_exists else None,
        csv_row_count=csv_rows,
        message=message,
    )


def run_streamlit_app() -> int:
    backend_dir = Path(__file__).resolve().parent
    app_path = backend_dir / 'app' / 'Homepage.py'

    if not app_path.exists():
        print(f'Streamlit app not found at {app_path}')
        return 2

    # Launch with the same interpreter to ensure correct environment
    cmd = [sys.executable, '-m', 'streamlit', 'run', str(app_path)]
    print(f'Starting Streamlit: {" ".join(cmd)} (cwd={backend_dir})')
    try:
        return subprocess.call(cmd, cwd=str(backend_dir))
    except FileNotFoundError:
        print(
            'Could not start Streamlit. Ensure Streamlit is installed in your environment (e.g., pip install streamlit).'
        )
        return 3


def main() -> None:
    # 1) Check database status
    status = get_database_status()
    print(status.message)

    # Provide a simple hint if the DB looks empty or missing
    if (
        not status.db_exists
        or not status.table_exists
        or (status.db_row_count or 0) == 0
    ):
        print(
            "Hint: You may need to generate the database. Try running 'python backend/app/Homepage.py' to load data."
        )

    # 2) Run Streamlit app
    exit_code = run_streamlit_app()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
