from pathlib import Path

import streamlit as st

from core.app_config import configs
from agent.langchain import generate_answer


st.set_page_config(page_title='HR AI Agent', page_icon='🤖', layout='wide')
st.title('HR AI Agent')
st.caption(
    'Ask data-grounded questions about the HR database. Answers come from `custom_db.db`.'
)


def reset_conversation():
    st.session_state.messages = []


if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'agent' in st.session_state:
    del st.session_state['agent']
if 'chat_input' not in st.session_state:
    st.session_state.chat_input = ''


with st.sidebar:
    st.button('Reset Chat', on_click=reset_conversation)
    st.subheader('Status')
    db_path = Path(configs.DB_PATH)
    if db_path.exists():
        st.success(f'Database found: {db_path.name}')
    else:
        st.error(
            'Database not found. Generate it from the Homepage or run the data load script.'
        )

    st.markdown('Examples:', unsafe_allow_html=True)
    examples = [
        'How many employees are in the Engineering department in New York?',
        'Which manager has the highest number of direct reports?',
        'What is the average tenure in the Sales department?',
        'Who are the top 3 longest-tenured employees in Marketing?',
        'List teams reporting to the Director of Operations in APAC',
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state.chat_input = ex
            st.rerun()


# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message['content'], unsafe_allow_html=True)


if prompt := st.chat_input('Ask your question about the HR database', key='chat_input'):
    with st.chat_message('user'):
        st.markdown(prompt, unsafe_allow_html=True)
    st.session_state.messages.append({'role': 'user', 'content': prompt})

    with st.chat_message('assistant'):
        with st.spinner('Thinking and querying the database...'):
            resp = generate_answer(prompt, history=st.session_state.messages)
            final_text = getattr(resp, 'content', str(resp))
            st.markdown(final_text, unsafe_allow_html=True)
    st.session_state.messages.append({'role': 'assistant', 'content': final_text})
