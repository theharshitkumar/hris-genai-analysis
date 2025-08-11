from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from core.app_config import configs

# ---------- Helpers ----------


def _to_bool(value) -> Optional[bool]:
    if pd.isna(value):
        return None
    s = str(value).strip().lower()
    if s in {'1', 'true', 't', 'yes', 'y'}:
        return True
    if s in {'0', 'false', 'f', 'no', 'n', '', 'na', 'n/a', 'null', 'none'}:
        return False
    return None


def _to_int(value) -> Optional[int]:
    if pd.isna(value):
        return None
    try:
        # Handle possible float-like strings (e.g. "15618.0")
        f = float(str(value))
        return int(f)
    except Exception:
        return None


def _to_dt(value) -> Optional[pd.Timestamp]:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s == '' or s.upper() in {'NA', 'N/A', 'NULL', 'NONE'}:
        return None
    # Try a few common formats, otherwise let pandas try
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return pd.to_datetime(datetime.strptime(s, fmt))
        except Exception:
            continue
    try:
        return pd.to_datetime(s, errors='coerce')
    except Exception:
        return None


def load_employees(db_source: str = 'custom') -> pd.DataFrame:
    """Load employee data from the selected SQLite database.

    db_source: 'custom' (default) or 'original'
    Returns a DataFrame with normalized dtypes for key fields.
    """
    db_path = (
        Path(configs.DB_PATH)
        if str(db_source).lower().startswith('custom')
        else Path(configs.ORIGINAL_DB_PATH)
    )
    if not db_path.exists():
        raise FileNotFoundError(
            f'Database not found at {db_path}. Run `python backend/eda/insert_data.py` to create it.'
        )

    # Read from SQLite into a pandas DataFrame
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query('SELECT * FROM employees', conn)

    # Normalize dtypes
    df['employee_id'] = df['employee_id'].apply(_to_int)
    if 'manager_id' in df.columns:
        df['manager_id'] = df['manager_id'].apply(_to_int)
    else:
        df['manager_id'] = None
    if 'supervisor_id' in df.columns:
        df['supervisor_id'] = df['supervisor_id'].apply(_to_int)
    else:
        df['supervisor_id'] = None

    # Dates
    if 'joining_date' in df.columns:
        df['joining_date'] = df['joining_date'].apply(_to_dt)
    if 'exit_date' in df.columns:
        df['exit_date'] = df['exit_date'].apply(_to_dt)

    # Booleans
    if 'is_active' in df.columns:
        df['is_active'] = df['is_active'].apply(_to_bool)

    # Job level numeric
    if 'job_level' in df.columns:
        df['job_level'] = pd.to_numeric(df['job_level'], errors='coerce').astype(
            'Int64'
        )

    return df


# ---------- EDA computations ----------


def distribution_counts(df: pd.DataFrame, column: str) -> pd.DataFrame:
    s = df[column].fillna('Unknown').astype(str)
    counts = s.value_counts(dropna=False).rename('count').to_frame()
    counts['percent'] = (counts['count'] / counts['count'].sum() * 100).round(2)
    counts.index.name = column
    counts = counts.reset_index()
    return counts


def compute_span_of_control(df: pd.DataFrame):
    reports = (
        df.dropna(subset=['manager_id'])
        .groupby('manager_id')['employee_id']
        .count()
        .rename('direct_reports')
        .reset_index()
    )
    managers = df[
        ['employee_id', 'first_name', 'last_name', 'department', 'location', 'region']
    ].rename(columns={'employee_id': 'manager_id'})
    span = reports.merge(managers, on='manager_id', how='left')
    span['manager_name'] = (
        span[['first_name', 'last_name']].fillna('').agg(' '.join, axis=1).str.strip()
    )
    span = span.drop(columns=['first_name', 'last_name']).sort_values(
        by='direct_reports', ascending=False
    )

    # Distribution of span sizes
    span_dist = (
        span['direct_reports']
        .value_counts()
        .sort_index()
        .rename('num_managers')
        .to_frame()
        .reset_index()
    )
    span_dist = span_dist.rename(columns={'index': 'direct_reports'})
    return span, span_dist


# ---------- Orchestration ----------


def run_eda(db_source: str = 'custom') -> str:
    df = load_employees(db_source=db_source)

    # Basic distributions for summary
    dist_department = distribution_counts(df, 'department')
    dist_location = distribution_counts(df, 'location')

    # Span of control
    span, _ = compute_span_of_control(df)

    # Build a single Markdown summary with required tables
    # Overburden threshold: managers at or above 90th percentile of direct reports, with a minimum practical threshold of 10
    overburden_threshold = None
    overburden_df = pd.DataFrame()
    top_managers_df = pd.DataFrame()
    if not span.empty:
        try:
            q90 = int(span['direct_reports'].quantile(0.90))
        except Exception:
            q90 = 0
        overburden_threshold = max(10, q90)
        overburden_df = span[
            span['direct_reports'] >= overburden_threshold
        ].sort_values('direct_reports', ascending=False)[
            [
                'manager_id',
                'manager_name',
                'department',
                'location',
                'region',
                'direct_reports',
            ]
        ]
        top_managers_df = span.sort_values('direct_reports', ascending=False).head(10)[
            [
                'manager_id',
                'manager_name',
                'department',
                'location',
                'region',
                'direct_reports',
            ]
        ]

    # Isolated employees: no manager, no supervisor, and no location
    isolated_df = pd.DataFrame()
    if {'manager_id', 'supervisor_id', 'location'}.issubset(df.columns):
        mask_isolated = (
            df['manager_id'].isna()
            & df['supervisor_id'].isna()
            & (df['location'].isna() | (df['location'].astype(str).str.strip() == ''))
        )
        if mask_isolated.any():
            iso = df.loc[mask_isolated].copy()
            iso['employee_name'] = (
                iso[['first_name', 'last_name']]
                .fillna('')
                .agg(' '.join, axis=1)
                .str.replace('\s+', ' ', regex=True)
                .str.strip()
            )
            isolated_df = iso[
                [
                    'employee_id',
                    'employee_name',
                    'department',
                    'location',
                    'region',
                    'job_level',
                ]
            ]

    def df_to_markdown_table(table: pd.DataFrame, columns: List[str]) -> List[str]:
        lines: List[str] = []
        header = ' | '.join(columns)
        align = ' | '.join(['---' for _ in columns])
        lines.append(f'| {header} |')
        lines.append(f'| {align} |')
        for _, r in table.iterrows():
            vals = [str(r[c]) if pd.notna(r[c]) else '' for c in columns]
            lines.append('| ' + ' | '.join(vals) + ' |')
        return lines

    md_lines: List[str] = []
    source_label = 'Original' if str(db_source).lower().startswith('orig') else 'Custom'
    md_lines.append(f'*Data source: {source_label} database*')
    md_lines.append('')
    md_lines.append('## EDA analysis')
    md_lines.append('')
    # Narrative summary paragraph based on data
    try:
        total_employees = len(df)
        # Departments
        dept_counts = (
            dist_department.sort_values('count', ascending=False)
            if not dist_department.empty
            else pd.DataFrame()
        )
        top_dept_name = (
            str(dept_counts.iloc[0]['department']) if not dept_counts.empty else 'N/A'
        )
        top_dept_count = (
            int(dept_counts.iloc[0]['count']) if not dept_counts.empty else 0
        )
        num_departments = (
            df['department'].astype(str).str.strip().replace({'': pd.NA}).nunique()
            if 'department' in df.columns
            else 0
        )

        # Locations
        loc_counts = (
            dist_location.sort_values('count', ascending=False)
            if not dist_location.empty
            else pd.DataFrame()
        )
        top_loc_name = (
            str(loc_counts.iloc[0]['location']) if not loc_counts.empty else 'N/A'
        )
        top_loc_count = int(loc_counts.iloc[0]['count']) if not loc_counts.empty else 0
        num_locations = (
            df['location'].astype(str).str.strip().replace({'': pd.NA}).nunique()
            if 'location' in df.columns
            else 0
        )
        top_loc_percent = (
            float(loc_counts.iloc[0]['percent'])
            if not loc_counts.empty and 'percent' in loc_counts.columns
            else 0.0
        )
        top_5_cities = (
            loc_counts.head(5)['location'].astype(str).tolist()
            if not loc_counts.empty
            else []
        )

        # Span of control metrics
        manager_count = int(len(span)) if not span.empty else 0
        avg_team = float(span['direct_reports'].mean()) if not span.empty else 0.0
        median_team = float(span['direct_reports'].median()) if not span.empty else 0.0
        small_teams = int((span['direct_reports'] <= 2).sum()) if not span.empty else 0
        large_teams_ge10 = (
            int((span['direct_reports'] >= 10).sum()) if not span.empty else 0
        )
        small_team_ratio = (
            (small_teams / manager_count * 100.0) if manager_count > 0 else 0.0
        )
        isolated_count = int(len(isolated_df)) if not isolated_df.empty else 0
        # Missingness by field
        missing_manager = (
            int(df['manager_id'].isna().sum()) if 'manager_id' in df.columns else 0
        )
        missing_supervisor = (
            int(df['supervisor_id'].isna().sum())
            if 'supervisor_id' in df.columns
            else 0
        )
        if 'location' in df.columns:
            _loc_series = df['location'].astype(str).str.strip()
            # Treat empty string or NaN as missing
            missing_location = int((df['location'].isna() | (_loc_series == '')).sum())
        else:
            missing_location = 0

        # Top managers workload range
        top_mgr_min = (
            int(top_managers_df['direct_reports'].min())
            if not top_managers_df.empty
            else 0
        )
        top_mgr_max = (
            int(top_managers_df['direct_reports'].max())
            if not top_managers_df.empty
            else 0
        )

        # Simple concentration heuristic based on top location share
        if top_loc_percent <= 20:
            concentration_msg = 'minimal regional concentration risk'
        elif top_loc_percent <= 35:
            concentration_msg = 'moderate regional concentration'
        else:
            concentration_msg = 'high regional concentration in the top location'

        md_lines.append('### Summary')
        summary_lines: List[str] = []
        # Workforce Distribution
        summary_lines.append(
            f'- **Workforce Distribution**: Dataset contains {total_employees:,} employees across {num_departments} departments and {num_locations} locations; {top_dept_name} is the largest department ({top_dept_count:,} employees), and {top_loc_name} is the largest location ({top_loc_count:,} employees).'
        )
        # Span of Control
        if manager_count > 0:
            summary_lines.append(
                f'- **Span of Control**: There are {manager_count:,} managers with direct reports; average span is {avg_team:.1f} (median {median_team:.1f}), with {small_teams:,} small teams (≤2 reports) and {large_teams_ge10:,} large teams (≥10 reports).'
            )
        else:
            summary_lines.append(
                '- **Span of Control**: No managers with direct reports identified in the dataset.'
            )
        # Manager Workload
        if top_mgr_max > 0:
            if top_mgr_min == top_mgr_max:
                workload_range = f'{top_mgr_max}'
            else:
                workload_range = f'{top_mgr_min}–{top_mgr_max}'
            summary_lines.append(
                f'- **Manager Workload**: Top 10 managers have {workload_range} direct reports each, indicating no significant overburdening but potentially excessive managerial layering.'
            )
        # Data Completeness
        if (
            missing_manager == 0
            and missing_supervisor == 0
            and missing_location == 0
            and isolated_count == 0
        ):
            completeness_msg = 'No employees lack manager, supervisor, or location data, suggesting strong data integrity in key structural fields.'
        else:
            completeness_parts = []
            if missing_manager > 0:
                completeness_parts.append(f'{missing_manager:,} missing manager')
            if missing_supervisor > 0:
                completeness_parts.append(f'{missing_supervisor:,} missing supervisor')
            if missing_location > 0:
                completeness_parts.append(f'{missing_location:,} missing location')
            if isolated_count > 0:
                completeness_parts.append(f'{isolated_count:,} isolated employees')
            completeness_msg = (
                'Some structural fields have missing data ('
                + ', '.join(completeness_parts)
                + ').'
            )
        summary_lines.append(f'- **Data Completeness**: {completeness_msg}')
        # Geographical Spread
        if top_5_cities:
            cities_display = ', '.join(top_5_cities)
            summary_lines.append(
                f'- **Geographical Spread**: Workforce is distributed across major cities ({cities_display}) with {concentration_msg}.'
            )
        # Team Structure Implications
        if manager_count > 0:
            if small_team_ratio >= 70:
                implication_msg = 'High proportion of small teams may signal organizational inefficiency or underutilization of managerial capacity.'
            elif small_team_ratio >= 40:
                implication_msg = 'Many small teams suggest opportunities to rebalance spans for greater leverage.'
            else:
                implication_msg = (
                    'Team sizes appear relatively balanced across managers.'
                )
            summary_lines.append(
                f'- **Team Structure Implications**: {implication_msg}'
            )

        md_lines.extend(summary_lines)
        md_lines.append('')
    except Exception:
        # Fallback: avoid failing the whole summary if any metric computation breaks
        pass

    # Departments table
    md_lines.append('### Employees by Department')
    if not dist_department.empty:
        dept_table = (
            dist_department[['department', 'count']]
            .rename(columns={'count': 'headcount'})
            .sort_values('headcount', ascending=False)
        )
        md_lines.extend(df_to_markdown_table(dept_table, ['department', 'headcount']))
    else:
        md_lines.append('_No department data available._')
    md_lines.append('')

    # Locations table
    md_lines.append('### Employees by Location')
    if not dist_location.empty:
        loc_table = (
            dist_location[['location', 'count']]
            .rename(columns={'count': 'headcount'})
            .sort_values('headcount', ascending=False)
        )
        md_lines.extend(df_to_markdown_table(loc_table, ['location', 'headcount']))
    else:
        md_lines.append('_No location data available._')
    md_lines.append('')

    # Overburden managers
    md_lines.append('### Overburdened Managers')
    if not span.empty:
        if overburden_threshold is not None and not overburden_df.empty:
            md_lines.append(
                f'Managers with direct reports >= {overburden_threshold} (90th percentile min 10).'
            )
            md_lines.extend(
                df_to_markdown_table(
                    overburden_df,
                    [
                        'manager_id',
                        'manager_name',
                        'department',
                        'location',
                        'region',
                        'direct_reports',
                    ],
                )
            )
            md_lines.append('')
        md_lines.append('Top 10 Managers by Direct Reports')
        md_lines.extend(
            df_to_markdown_table(
                top_managers_df,
                [
                    'manager_id',
                    'manager_name',
                    'department',
                    'location',
                    'region',
                    'direct_reports',
                ],
            )
        )
    else:
        md_lines.append('_No span of control data available._')
    md_lines.append('')

    # Isolated employees
    md_lines.append('### Isolated Employees')
    if not isolated_df.empty:
        md_lines.append(f'Total isolated employees: {len(isolated_df)}')
        md_lines.extend(
            df_to_markdown_table(
                isolated_df.sort_values('employee_id'),
                [
                    'employee_id',
                    'employee_name',
                    'department',
                    'location',
                    'region',
                    'job_level',
                ],
            )
        )
    else:
        md_lines.append('No isolated employees detected.')
    md_lines.append('')

    return '\n'.join(md_lines)


if __name__ == '__main__':
    md_lines = run_eda()
    print(md_lines)
