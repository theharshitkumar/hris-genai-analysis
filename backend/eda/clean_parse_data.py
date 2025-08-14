import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from core.app_config import configs


DB_PATH = Path(configs.DB_PATH)


# ---------- Shared helpers ----------


def _candidate_ids_for_level(
    cursor: sqlite3.Cursor,
    department: str,
    target_level: int,
    region: Optional[str],
    location: Optional[str],
) -> List[int]:
    # Try most specific → least specific fallbacks
    queries = [
        (
            'SELECT employee_id FROM employees WHERE department = ? AND job_level = ? AND region = ? AND location = ?',
            (department, str(target_level), region, location),
        ),
        (
            'SELECT employee_id FROM employees WHERE department = ? AND job_level = ? AND region = ?',
            (department, str(target_level), region),
        ),
        (
            'SELECT employee_id FROM employees WHERE department = ? AND job_level = ?',
            (department, str(target_level)),
        ),
    ]
    for sql, params in queries:
        rows = cursor.execute(sql, params).fetchall()
        if rows:
            return [r[0] for r in rows]  # flatten the list of tuples
    return []


def _choose_least_loaded(
    cursor: sqlite3.Cursor,
    candidate_ids: List[int],
    subordinate_col: str,  # 'manager_id' or 'supervisor_id'
) -> Optional[int]:
    if not candidate_ids:
        return None
    best_id = None
    best_count = float('inf')
    for cid in candidate_ids:
        cnt = cursor.execute(
            f'SELECT COUNT(*) FROM employees WHERE {subordinate_col} = ?',
            (cid,),
        ).fetchone()[0]
        if cnt < best_count:
            best_count = cnt
            best_id = cid
    return best_id


def _find_leader(
    cursor: sqlite3.Cursor,
    department: str,
    job_level: int,
    region: Optional[str],
    location: Optional[str],
    level_offset: int,
    subordinate_col: str,
) -> Optional[int]:
    target_level = int(job_level) + level_offset
    candidates = _candidate_ids_for_level(
        cursor, department, target_level, region, location
    )
    return _choose_least_loaded(cursor, candidates, subordinate_col)


def _is_valid_leader_id(
    cursor: sqlite3.Cursor,
    department: str,
    job_level: int,
    region: Optional[str],
    location: Optional[str],
    leader_id: Optional[int],
    level_offset: int,
) -> bool:
    if leader_id is None:
        return False
    target_level = int(job_level) + level_offset
    candidates = _candidate_ids_for_level(
        cursor, department, target_level, region, location
    )

    return leader_id in candidates


# ---------- Steps ----------


def validate_manager_id_supervisor_id(cursor: sqlite3.Cursor) -> None:
    rows = cursor.execute(
        'SELECT employee_id,department,job_level,region,location,manager_id,supervisor_id '
        'FROM employees WHERE manager_id IS NOT NULL OR supervisor_id IS NOT NULL'
    ).fetchall()

    print(f'[1/4] Validating manager/supervisor IDs on {len(rows)} employees...')
    cleared_mgr = 0
    cleared_sup = 0

    for i, (
        employee_id,
        department,
        job_level,
        region,
        location,
        manager_id,
        supervisor_id,
    ) in enumerate(rows, 1):
        jl = int(job_level)

        # Manager must be at level +1
        if manager_id is not None:
            if not _is_valid_leader_id(
                cursor, department, jl, region, location, manager_id, level_offset=1
            ):
                cursor.execute(
                    'UPDATE employees SET manager_id = NULL WHERE employee_id = ?',
                    (employee_id,),
                )
                cleared_mgr += 1

        # Supervisor must be at level +2 (aligns with assignment step)
        if supervisor_id is not None:
            if not _is_valid_leader_id(
                cursor, department, jl, region, location, supervisor_id, level_offset=2
            ):
                cursor.execute(
                    'UPDATE employees SET supervisor_id = NULL WHERE employee_id = ?',
                    (employee_id,),
                )
                cleared_sup += 1
        if i % 1000 == 0:
            print(f'  - processed {i}/{len(rows)}')

    print(
        f'  -> cleared invalid manager_id: {cleared_mgr}, supervisor_id: {cleared_sup}'
    )


def update_employees_tenure(cursor: sqlite3.Cursor) -> None:
    def parse_date(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        s = str(value).strip()
        if s == '' or s.upper() in {'NA', 'N/A', 'NULL', 'NONE'}:
            return None
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        if len(s) >= 10:
            try:
                _ = datetime.strptime(s[:10], '%Y-%m-%d')
                return s[:10]
            except Exception:
                pass
        return None

    def compute_tenure(joining: str, exit_: Optional[str]) -> float:
        start = datetime.strptime(joining, '%Y-%m-%d').date()
        end = datetime.strptime(exit_, '%Y-%m-%d').date() if exit_ else date.today()
        return round((end - start).days / 365.25, 2)

    rows = cursor.execute(
        'SELECT employee_id, joining_date, exit_date FROM employees'
    ).fetchall()
    print(f'[2/4] Updating tenure for {len(rows)} employees...')

    updates = []
    for i, (employee_id, joining_raw, exit_raw) in enumerate(rows, 1):
        joining_norm = parse_date(joining_raw)
        exit_norm = parse_date(exit_raw)
        tenure = compute_tenure(joining_norm, exit_norm)
        updates.append((joining_norm, exit_norm, tenure, employee_id))

        if i % 1000 == 0:
            print(f'  - prepared {i}/{len(rows)} updates')

    cursor.executemany(
        'UPDATE employees SET joining_date = ?, exit_date = ?, tenure_years = ? WHERE employee_id = ?',
        updates,
    )
    print(f'  -> tenure updated for {len(updates)} employees')


def update_employees_manager_id(cursor: sqlite3.Cursor) -> None:
    rows = cursor.execute(
        'SELECT employee_id,department,job_level,region,location FROM employees WHERE manager_id IS NULL'
    ).fetchall()
    print(f'[3/4] Filling missing manager_id for {len(rows)} employees...')

    updated = 0
    skipped = 0

    for i, (employee_id, department, job_level, region, location) in enumerate(rows, 1):
        jl = int(job_level) if job_level is not None else 0
        if jl == 5:
            skipped += 1
            continue

        manager_id = _find_leader(
            cursor,
            department,
            jl,
            region,
            location,
            level_offset=1,
            subordinate_col='manager_id',
        )
        if manager_id is not None:
            cursor.execute(
                'UPDATE employees SET manager_id = ? WHERE employee_id = ?',
                (manager_id, employee_id),
            )
            updated += 1

        if i % 1000 == 0:
            print(f'  - processed {i}/{len(rows)}')

    print(f'  -> manager_id set: {updated}, skipped (level 5): {skipped}')


def update_employees_supervisor_id(cursor: sqlite3.Cursor) -> None:
    rows = cursor.execute(
        'SELECT employee_id,department,job_level,region,location FROM employees WHERE supervisor_id IS NULL'
    ).fetchall()
    print(f'[4/4] Assigning supervisor_id for {len(rows)} employees...')

    updated = 0
    skipped = 0

    for i, (employee_id, department, job_level, region, location) in enumerate(rows, 1):
        jl = int(job_level) if job_level is not None else 0
        if jl == 4:
            skipped += 1
            continue

        supervisor_id = _find_leader(
            cursor,
            department,
            jl,
            region,
            location,
            level_offset=2,
            subordinate_col='supervisor_id',
        )
        if supervisor_id is not None:
            cursor.execute(
                'UPDATE employees SET supervisor_id = ? WHERE employee_id = ?',
                (supervisor_id, employee_id),
            )
            updated += 1

        if i % 1000 == 0:
            print(f'  - processed {i}/{len(rows)}')

    print(f'  -> supervisor_id set: {updated}, skipped (level 4): {skipped}')


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f'Database not found at {DB_PATH}. Run the data load first.'
        )

    print(f'Opening database at {DB_PATH}...')
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        validate_manager_id_supervisor_id(cursor)
        conn.commit()
        print('Step 1 done.')

        update_employees_tenure(cursor)
        conn.commit()
        print('Step 2 done.')

        update_employees_manager_id(cursor)
        conn.commit()
        print('Step 3 done.')

        update_employees_supervisor_id(cursor)
        conn.commit()
        print('Step 4 done. All processing complete.')


if __name__ == '__main__':
    main()
