import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from core.app_config import configs


DB_PATH = Path(configs.DB_PATH)
CSV_PATH = Path(configs.CSV_PATH)
ORIGINAL_DB_PATH = Path(configs.ORIGINAL_DB_PATH)


def parse_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s == '' or s.upper() in {'NA', 'N/A', 'NULL', 'NONE'}:
        return None
    # Try common formats, output as YYYY-MM-DD
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    # Fallback: return original if it looks ISO-like
    return s


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    if s == '' or s.upper() in {'NA', 'N/A', 'NULL', 'NONE'}:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if s == '' or s.upper() in {'NA', 'N/A', 'NULL', 'NONE'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_bool_to_int(value: Optional[str]) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    if s in {'1', 'true', 't', 'yes', 'y'}:
        return True
    if s in {'0', 'false', 'f', 'no', 'n', '', 'na', 'n/a', 'null', 'none'}:
        return False
    return False


def parse_text(value: Optional[str], required: bool = False) -> Optional[str]:
    if value is None:
        return '' if required else None
    s = str(value).strip()
    if required:
        return s  # may be empty if CSV is bad; DB NOT NULL will enforce
    return s if s != '' else None


def create_employees_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute('DROP TABLE IF EXISTS employees')
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
          employee_id INTEGER PRIMARY KEY,
          first_name TEXT NOT NULL,
          last_name TEXT NOT NULL,
          department TEXT,
          job_title TEXT,
          job_level INTEGER,
          location TEXT,
          region TEXT,
          manager_id INTEGER,
          joining_date TEXT NOT NULL,
          exit_date TEXT,
          performance_rating INTEGER,
          tenure_years FLOAT,
          is_active BOOLEAN,
          supervisor_id INTEGER
        );
        """
    )


def load_csv_and_insert(cursor: sqlite3.Cursor, csv_path: Path) -> int:
    count = 0
    with csv_path.open('r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        rows = []
        for row in reader:
            rows.append(
                (
                    parse_int(row.get('employee_id')),
                    parse_text(row.get('first_name'), required=True),
                    parse_text(row.get('last_name'), required=True),
                    parse_text(row.get('department')),
                    parse_text(row.get('job_title')),
                    parse_int(row.get('job_level')),
                    parse_text(row.get('location')),
                    parse_text(row.get('region')),
                    parse_int(row.get('manager_id')),
                    parse_date(row.get('joining_date')),
                    parse_date(row.get('exit_date')),
                    parse_int(row.get('performance_rating')),
                    parse_float(row.get('tenure_years')),
                    parse_bool_to_int(row.get('is_active')),
                    parse_int(row.get('supervisor_id')),
                )
            )

        insert_sql = (
            'INSERT OR REPLACE INTO employees ('
            'employee_id, first_name, last_name, department, job_title, job_level, '
            'location, region, manager_id, joining_date, exit_date, performance_rating, '
            'tenure_years, is_active, supervisor_id) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
        )
        cursor.executemany(insert_sql, rows)
        count = len(rows)
    return count


def create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        cursor = conn.cursor()
        create_employees_table(cursor)

        inserted = load_csv_and_insert(cursor, CSV_PATH)
        conn.commit()

        # Simple verification/summary
        cur = conn.execute('SELECT COUNT(*) FROM employees')
        total = cur.fetchone()[0]
        print(f'Inserted/updated rows: {inserted}')
        print(f'Total rows in employees: {total}')
        print(f'SQLite DB: {path}')
        print(f'CSV source: {CSV_PATH}')


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f'CSV file not found at {CSV_PATH}')
    create_db(DB_PATH)
    create_db(ORIGINAL_DB_PATH)


if __name__ == '__main__':
    main()
