from pathlib import Path
import sqlite3
import streamlit as st
from core.app_config import configs
from core.env import env


st.set_page_config(
    page_title='Beta Corp Intelligence Assistant',
    page_icon='📊',
    layout='wide',
)

st.title('Beta Corp Intelligence Assistant')
st.caption(
    'HR Analytics prototype — explore EDA visuals and ask data-grounded questions'
)


# ------------------------------
# Helpers
# ------------------------------
def get_employee_count(db_path_str: str) -> int | None:
    path = Path(db_path_str)
    if not path.exists():
        return None
    try:
        with sqlite3.connect(path) as conn:
            cur = conn.execute('SELECT COUNT(*) FROM employees')
            return int(cur.fetchone()[0])
    except Exception:
        return None


custom_rows = get_employee_count(configs.DB_PATH)
orig_rows = get_employee_count(configs.ORIGINAL_DB_PATH)
has_llm_config = bool(
    env.AZURE_OPENAI_API_KEY
    and env.AZURE_OPENAI_ENDPOINT
    and env.AZURE_OPENAI_API_VERSION
    and env.AZURE_OPENAI_DEPLOYMENT
)


# ------------------------------
# Hero actions
# ------------------------------
cta1, cta2 = st.columns(2)
with cta1:
    st.page_link('pages/HR AI agent.py', label='Open HR AI Agent', icon='🤖')
with cta2:
    st.page_link('pages/EDA analysis.py', label='Open EDA Analysis', icon='📈')


# ------------------------------
# System status
# ------------------------------
st.subheader('System status')
st.write('Quick health check for data and model configuration:')

s1, s2, s3 = st.columns(3)
with s1:
    if custom_rows is not None:
        st.success('Custom DB: available')
        st.metric('Employees (custom)', f'{custom_rows:,}')
    else:
        st.error('Custom DB: not found')
        st.caption(f'Expected at: `{Path(configs.DB_PATH)}`')
with s2:
    if orig_rows is not None:
        st.success('Original DB: available')
        st.metric('Employees (original)', f'{orig_rows:,}')
    else:
        st.warning('Original DB: not found')
        st.caption(f'Expected at: `{Path(configs.ORIGINAL_DB_PATH)}`')
with s3:
    if has_llm_config:
        st.success('LLM config: set (Azure OpenAI)')
    else:
        st.warning('LLM config: missing')
        st.caption('Check .env for Azure OpenAI keys and deployment details')


# ------------------------------
# Quick start
# ------------------------------
st.subheader('Quick start')
if custom_rows is None:
    st.markdown('Create the SQLite databases from the CSV before exploring:')
    st.code('python backend/eda/insert_data.py', language='bash')
else:
    st.markdown('Databases are ready. Jump in with an example question:')

examples = [
    'How many employees are in the Engineering department in New York?',
    'Which manager has the highest number of direct reports?',
    'What is the average tenure in the Sales department?',
    'Who are the top 3 longest-tenured employees in Marketing?',
    'List teams reporting to the Director of Operations in APAC',
]

ex_cols = st.columns(2)
for idx, ex in enumerate(examples):
    with ex_cols[idx % 2]:
        if st.button(ex, use_container_width=True, key=f'ex_{idx}'):
            st.session_state['chat_input'] = ex
            try:
                # Navigate to the HR AI agent page with the prompt pre-filled
                st.switch_page('pages/HR AI agent.py')
            except Exception:
                st.info(
                    'Open the HR AI Agent page from the navigation to use this prompt.'
                )


# ------------------------------
# Explore section
# ------------------------------
st.subheader('Explore')
st.markdown('- Use the HR AI Agent for natural-language questions on the HR database.')
st.markdown('- Use the EDA Analysis page for interactive charts and summaries.')
