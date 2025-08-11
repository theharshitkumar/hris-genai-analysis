from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd
import sqlite3

from core.app_config import configs


def _get_db_path(db_source: str = 'custom') -> Path:
    if str(db_source).lower().startswith('orig'):
        return Path(configs.ORIGINAL_DB_PATH)
    return Path(configs.DB_PATH)


def _connect(db_source: str = 'custom') -> sqlite3.Connection:
    db_path = _get_db_path(db_source)
    if not db_path.exists():
        raise FileNotFoundError(
            f'Database not found at {db_path}. Run `python backend/eda/insert_data.py` to create it.'
        )
    return sqlite3.connect(db_path)


def fetch_unique_regions(db_source: str = 'custom') -> List[str]:
    sql = """
        SELECT DISTINCT region
        FROM employees
        WHERE region IS NOT NULL AND TRIM(region) <> ''
        ORDER BY region
    """
    with _connect(db_source) as conn:
        rows = conn.execute(sql).fetchall()
    return [r[0] for r in rows]


def fetch_unique_locations(db_source: str = 'custom') -> List[str]:
    sql = """
        SELECT DISTINCT location
        FROM employees
        WHERE location IS NOT NULL AND TRIM(location) <> ''
        ORDER BY location
    """
    with _connect(db_source) as conn:
        rows = conn.execute(sql).fetchall()
    return [r[0] for r in rows]


def fetch_unique_departments(db_source: str = 'custom') -> List[str]:
    sql = """
        SELECT DISTINCT department
        FROM employees
        WHERE department IS NOT NULL AND TRIM(department) <> ''
        ORDER BY department
    """
    with _connect(db_source) as conn:
        rows = conn.execute(sql).fetchall()
    return [r[0] for r in rows]


def department_headcount(
    region: Optional[str] = None,
    location: Optional[str] = None,
    *,
    db_source: str = 'custom',
) -> pd.DataFrame:
    """Return department-wise headcounts, optionally filtered by region or location.

    If both region and location are provided, location takes precedence.
    """
    where_clause = []
    params: List[str] = []
    if location:
        where_clause.append('location = ?')
        params.append(location)
    elif region:
        where_clause.append('region = ?')
        params.append(region)

    where_sql = f'WHERE {" AND ".join(where_clause)}' if where_clause else ''
    sql = f"""
        SELECT COALESCE(department, 'Unknown') AS department,
               COUNT(*) AS headcount
        FROM employees
        {where_sql}
        GROUP BY COALESCE(department, 'Unknown')
        ORDER BY headcount DESC, department ASC
    """

    with _connect(db_source) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df


def fetch_manager_team_sizes(
    *,
    region: Optional[str] = None,
    location: Optional[str] = None,
    department: Optional[str] = None,
    db_source: str = 'custom',
) -> pd.DataFrame:
    """Return team sizes per manager with optional filters applied to direct reports.

    Filters (if provided) are applied to the direct reports' attributes, not manager records.
    Returns columns: manager_id, manager_name, team_size.
    """
    where_clause: List[str] = ['e.manager_id IS NOT NULL']
    params: List[str] = []
    if location:
        where_clause.append('e.location = ?')
        params.append(location)
    if region:
        where_clause.append('e.region = ?')
        params.append(region)
    if department:
        where_clause.append('e.department = ?')
        params.append(department)

    where_sql = ' AND '.join(where_clause)
    sql = f"""
        SELECT
            e.manager_id AS manager_id,
            TRIM(COALESCE(m.first_name, '')) || CASE WHEN TRIM(COALESCE(m.first_name, '')) <> '' AND TRIM(COALESCE(m.last_name, '')) <> '' THEN ' ' ELSE '' END || TRIM(COALESCE(m.last_name, '')) AS manager_name,
            COUNT(e.employee_id) AS team_size
        FROM employees e
        LEFT JOIN employees m ON m.employee_id = e.manager_id
        WHERE {where_sql}
        GROUP BY e.manager_id, manager_name
        HAVING COUNT(e.employee_id) > 0
        ORDER BY team_size DESC
    """
    with _connect(db_source) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df


def fetch_attrition_by_month(
    *,
    region: Optional[str] = None,
    location: Optional[str] = None,
    department: Optional[str] = None,
    db_source: str = 'custom',
) -> pd.DataFrame:
    """Return monthly attrition counts as a DataFrame with columns: ym, attritions.

    Filters are applied to the attritted employees' attributes.
    """
    where_clause: List[str] = [
        'exit_date IS NOT NULL',
        'COALESCE(is_active, 0) = 0',
    ]
    params: List[str] = []
    if location:
        where_clause.append('location = ?')
        params.append(location)
    if region:
        where_clause.append('region = ?')
        params.append(region)
    if department:
        where_clause.append('department = ?')
        params.append(department)

    where_sql = ' AND '.join(where_clause)
    sql = f"""
        SELECT strftime('%Y-%m', exit_date) AS ym,
               COUNT(*) AS attritions
        FROM employees
        WHERE {where_sql}
        GROUP BY ym
        ORDER BY ym
    """
    with _connect(db_source) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df


def fetch_attrition_by_year(
    *,
    region: Optional[str] = None,
    location: Optional[str] = None,
    department: Optional[str] = None,
    db_source: str = 'custom',
) -> pd.DataFrame:
    """Return yearly attrition counts as a DataFrame with columns: year, attritions."""
    where_clause: List[str] = [
        'exit_date IS NOT NULL',
        'COALESCE(is_active, 0) = 0',
    ]
    params: List[str] = []
    if location:
        where_clause.append('location = ?')
        params.append(location)
    if region:
        where_clause.append('region = ?')
        params.append(region)
    if department:
        where_clause.append('department = ?')
        params.append(department)

    where_sql = ' AND '.join(where_clause)
    sql = f"""
        SELECT strftime('%Y', exit_date) AS year,
               COUNT(*) AS attritions
        FROM employees
        WHERE {where_sql}
        GROUP BY year
        ORDER BY year
    """
    with _connect(db_source) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df
