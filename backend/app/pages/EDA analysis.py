from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st

from core.app_config import configs
from eda.runtime_queries import (
    department_headcount,
    fetch_unique_locations,
    fetch_unique_regions,
    fetch_unique_departments,
    fetch_manager_team_sizes,
    fetch_attrition_by_month,
    fetch_attrition_by_year,
)
from eda.eda_analysis import run_eda


st.set_page_config(page_title='EDA analysis', page_icon='📈', layout='wide')
st.title('EDA analysis')


outputs_dir = Path(configs.BASE_PATH) / 'eda' / 'outputs'


summary_md_path = outputs_dir / 'eda_summary.md'
summary_md = (
    summary_md_path.read_text(encoding='utf-8') if summary_md_path.exists() else ''
)

(tab_summary, tab_dept_headcount, tab_team_size, tab_attrition) = st.tabs(
    [
        'EDA analysis',
        'Department-wise headcount',
        'Team Size distribution',
        'Attrition trend',
    ]
)

with tab_summary:
    src_col_sum, _ = st.columns([1, 3])
    with src_col_sum:
        sum_source_label = st.selectbox(
            'Data source', ['Custom (current)', 'Original'], index=0, key='sum_db'
        )
    db_source_sum = 'original' if sum_source_label.startswith('Original') else 'custom'
    markdown_summary = run_eda(db_source_sum)
    st.markdown(markdown_summary)

with tab_dept_headcount:
    st.subheader('Department-wise headcount')

    # Persist last computed result so dropdown changes do not auto-update the chart
    if 'dept_headcount_df' not in st.session_state:
        st.session_state['dept_headcount_df'] = None

    # Data source selector
    src_col, _ = st.columns([1, 3])
    with src_col:
        dept_source_label = st.selectbox(
            'Data source', ['Custom (current)', 'Original'], index=0, key='dept_db'
        )
    db_source_dept = (
        'original' if dept_source_label.startswith('Original') else 'custom'
    )

    scope = st.selectbox(
        'Filter scope', ['Global', 'Region', 'Location'], key='dept_scope'
    )
    selected_region = None
    selected_location = None
    if scope == 'Region':
        regions = fetch_unique_regions(db_source_dept)
        selected_region = st.selectbox(
            'Select region', options=['All'] + regions, index=0, key='dept_region'
        )
        if selected_region == 'All':
            selected_region = None
    elif scope == 'Location':
        locations = fetch_unique_locations(db_source_dept)
        selected_location = st.selectbox(
            'Select location', options=['All'] + locations, index=0, key='dept_location'
        )
        if selected_location == 'All':
            selected_location = None

    run_btn = st.button('Run', key='run_dept_headcount')

    if scope == 'Global':
        region_arg = None
        location_arg = None
    elif scope == 'Region':
        region_arg = selected_region
        location_arg = None
    else:
        region_arg = None
        location_arg = selected_location

    if run_btn:
        try:
            df = department_headcount(
                region=region_arg, location=location_arg, db_source=db_source_dept
            )
            st.session_state['dept_headcount_df'] = df
        except Exception as exc:  # noqa: BLE001
            st.session_state['dept_headcount_df'] = None
            st.error(f'Failed to load data: {exc}')

    result_df = st.session_state.get('dept_headcount_df')
    if result_df is None or result_df.empty:
        st.info('Choose filters and click Run to generate the chart.')
    else:
        chart = (
            alt.Chart(result_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    'department:N',
                    sort='-y',
                    axis=alt.Axis(labelAngle=-25, labelOverlap=True, labelLimit=300),
                ),
                y=alt.Y('headcount:Q'),
                tooltip=['department', 'headcount'],
            )
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)
        st.dataframe(result_df, use_container_width=True, hide_index=True)

with tab_team_size:
    st.subheader('Team Size distribution (Span of Control)')

    if 'team_size_df' not in st.session_state:
        st.session_state['team_size_df'] = None

    # Data source selector
    src_col2, _ = st.columns([1, 3])
    with src_col2:
        team_source_label = st.selectbox(
            'Data source', ['Custom (current)', 'Original'], index=0, key='team_db'
        )
    db_source_team = (
        'original' if team_source_label.startswith('Original') else 'custom'
    )

    scope = st.selectbox(
        'Filter scope', ['Global', 'Region', 'Location', 'Department'], key='team_scope'
    )
    selected_region = None
    selected_location = None
    selected_department = None
    if scope == 'Region':
        regions = fetch_unique_regions(db_source_team)
        selected_region = st.selectbox(
            'Select region', options=['All'] + regions, index=0, key='team_region'
        )
        if selected_region == 'All':
            selected_region = None
    elif scope == 'Location':
        locations = fetch_unique_locations(db_source_team)
        selected_location = st.selectbox(
            'Select location', options=['All'] + locations, index=0, key='team_location'
        )
        if selected_location == 'All':
            selected_location = None
    elif scope == 'Department':
        depts = fetch_unique_departments(db_source_team)
        selected_department = st.selectbox(
            'Select department', options=['All'] + depts, index=0, key='team_department'
        )
        if selected_department == 'All':
            selected_department = None

    run_btn = st.button('Run', key='run_team_size')

    region_arg = None
    location_arg = None
    department_arg = None
    if scope == 'Region':
        region_arg = selected_region
    elif scope == 'Location':
        location_arg = selected_location
    elif scope == 'Department':
        department_arg = selected_department

    if run_btn:
        try:
            sizes_df = fetch_manager_team_sizes(
                region=region_arg,
                location=location_arg,
                department=department_arg,
                db_source=db_source_team,
            )
            st.session_state['team_size_df'] = sizes_df
        except Exception as exc:  # noqa: BLE001
            st.session_state['team_size_df'] = None
            st.error(f'Failed to load team size distribution: {exc}')

    sizes_df = st.session_state.get('team_size_df')
    if sizes_df is None or sizes_df.empty:
        st.info('Choose filters and click Run to generate the distribution.')
    else:
        max_size = int(sizes_df['team_size'].max())
        num_bins = min(20, max_size) if max_size > 0 else 1
        chart = (
            alt.Chart(sizes_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    'team_size:Q',
                    bin=alt.Bin(maxbins=num_bins),
                    title='Team Size (Span of Control)',
                ),
                y=alt.Y('count()', title='Number of Managers'),
                tooltip=[
                    alt.Tooltip('count()', title='Managers'),
                    alt.Tooltip(
                        'team_size:Q',
                        bin=alt.Bin(maxbins=num_bins),
                        title='Team Size bin',
                    ),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(chart, use_container_width=True)
        st.dataframe(
            sizes_df[['manager_id', 'manager_name', 'team_size']].sort_values(
                'team_size', ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_attrition:
    st.subheader('Attrition trend')

    if 'attr_month_df' not in st.session_state:
        st.session_state['attr_month_df'] = None
    if 'attr_year_df' not in st.session_state:
        st.session_state['attr_year_df'] = None

    # Data source selector
    src_col3, _ = st.columns([1, 3])
    with src_col3:
        attr_source_label = st.selectbox(
            'Data source', ['Custom (current)', 'Original'], index=0, key='attr_db'
        )
    db_source_attr = (
        'original' if attr_source_label.startswith('Original') else 'custom'
    )

    scope = st.selectbox(
        'Filter scope', ['Global', 'Region', 'Location', 'Department'], key='attr_scope'
    )
    selected_region = None
    selected_location = None
    selected_department = None
    if scope == 'Region':
        regions = fetch_unique_regions(db_source_attr)
        selected_region = st.selectbox(
            'Select region', options=['All'] + regions, index=0, key='attr_region'
        )
        if selected_region == 'All':
            selected_region = None
    elif scope == 'Location':
        locations = fetch_unique_locations(db_source_attr)
        selected_location = st.selectbox(
            'Select location', options=['All'] + locations, index=0, key='attr_location'
        )
        if selected_location == 'All':
            selected_location = None
    elif scope == 'Department':
        depts = fetch_unique_departments(db_source_attr)
        selected_department = st.selectbox(
            'Select department', options=['All'] + depts, index=0, key='attr_department'
        )
        if selected_department == 'All':
            selected_department = None

    run_btn = st.button('Run', key='run_attrition')

    region_arg = None
    location_arg = None
    department_arg = None
    if scope == 'Region':
        region_arg = selected_region
    elif scope == 'Location':
        location_arg = selected_location
    elif scope == 'Department':
        department_arg = selected_department

    if run_btn:
        try:
            mdf = fetch_attrition_by_month(
                region=region_arg,
                location=location_arg,
                department=department_arg,
                db_source=db_source_attr,
            )
            ydf = fetch_attrition_by_year(
                region=region_arg,
                location=location_arg,
                department=department_arg,
                db_source=db_source_attr,
            )
            st.session_state['attr_month_df'] = mdf
            st.session_state['attr_year_df'] = ydf
        except Exception as exc:  # noqa: BLE001
            st.session_state['attr_month_df'] = None
            st.session_state['attr_year_df'] = None
            st.error(f'Failed to load attrition trend: {exc}')

    mdf = st.session_state.get('attr_month_df')
    ydf = st.session_state.get('attr_year_df')
    if (mdf is None or mdf.empty) and (ydf is None or ydf.empty):
        st.info('Choose filters and click Run to generate the attrition trend charts.')
    else:
        if mdf is not None and not mdf.empty:
            try:
                mdf_plot = mdf.copy()
                # Try to coerce to datetime for proper x-axis ordering
                mdf_plot['ym'] = pd.to_datetime(
                    mdf_plot['ym'], format='%Y-%m', errors='coerce'
                )
            except Exception:
                mdf_plot = mdf
            line_month = (
                alt.Chart(mdf_plot)
                .mark_line(point=True)
                .encode(
                    x=alt.X('ym:T', title='Month'),
                    y=alt.Y('attritions:Q', title='Attritions'),
                    tooltip=['ym', 'attritions'],
                )
                .properties(height=300, title='Monthly attrition trend')
            )
            st.altair_chart(line_month, use_container_width=True)

        if ydf is not None and not ydf.empty:
            line_year = (
                alt.Chart(ydf)
                .mark_line(point=True)
                .encode(
                    x=alt.X('year:O', title='Year'),
                    y=alt.Y('attritions:Q', title='Attritions'),
                    tooltip=['year', 'attritions'],
                )
                .properties(height=300, title='Yearly attrition trend')
            )
            st.altair_chart(line_year, use_container_width=True)
