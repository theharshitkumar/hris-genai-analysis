from typing import Optional, List, Dict

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

from agent.function_tools import (
    get_columns_descriptions,
    get_today_date,
    sql_agent_tools,
)
from agent.langchain_providers import lc_providers
from agent.agent_constant import (
    SQL_GENERATION_SYSTEM_PROMPT,
    ANSWER_SYNTHESIS_TEMPLATE,
    SQL_REPAIR_PROMPT_TEMPLATE,
    FALLBACK_GENERAL_PROMPT_TEMPLATE,
)

db = lc_providers.db
llm = lc_providers.llm
llm = llm.bind_tools(sql_agent_tools())


class QueryOutput(BaseModel):
    query: str = Field(..., description='Syntactically valid SQL query.')


def _normalize_content(raw: object) -> str:
    if isinstance(raw, str):
        return raw
    if hasattr(raw, 'content'):
        try:
            value = getattr(raw, 'content')
            if isinstance(value, str):
                return value
        except Exception:
            pass
    if isinstance(raw, dict) and 'content' in raw:
        value = raw.get('content')
        if isinstance(value, str):
            return value
    return str(raw)


def _convert_history_to_messages(history: Optional[List[Dict[str, object]]]):
    if not history:
        return []
    converted = []
    for msg in history:
        role = msg.get('role')
        content = _normalize_content(msg.get('content', ''))
        if not content:
            continue
        if role == 'user':
            converted.append(HumanMessage(content=content))
        elif role == 'assistant':
            converted.append(AIMessage(content=content))
    return converted


def generate_answer(
    question: str, history: Optional[List[Dict[str, str]]] = None, max_retries: int = 2
) -> str:
    """Generate SQL for question, execute it with repair loop, and return final answer.

    history: Optional list of chat messages as dicts with keys 'role' and 'content'.
    """

    db_tool = QuerySQLDatabaseTool(db=db)
    structured_llm = llm.with_structured_output(QueryOutput)

    # 1) Generate SQL
    columns_descriptions = get_columns_descriptions('')
    today_date = get_today_date('')
    history_messages = _convert_history_to_messages(history)
    prompt = ChatPromptTemplate(
        [
            ('system', SQL_GENERATION_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name='history'),
            ('user', 'Question: {input}'),
        ]
    ).invoke(
        {
            'dialect': db.dialect,
            'top_k': 10,
            'table_info': db.get_table_info(),
            'input': question,
            'columns_descriptions': columns_descriptions,
            'today_date': today_date,
            'history': history_messages,
        }
    )

    sql_obj = structured_llm.invoke(prompt)
    if isinstance(sql_obj, dict):
        sql_query = sql_obj.get('query', '').strip()
    else:
        if hasattr(sql_obj, 'model_dump'):
            sql_query = (sql_obj.model_dump().get('query', '')).strip()
        else:
            value = getattr(sql_obj, 'query', '')
            sql_query = value.strip() if isinstance(value, str) else ''

    if not sql_query:
        fallback = FALLBACK_GENERAL_PROMPT_TEMPLATE.format(
            question=question, error_section=''
        )
        resp = llm.invoke(fallback)
        return getattr(resp, 'content', str(resp))

    # 2) Execute with repair
    attempt = 0
    last_error: Optional[str] = None
    current_sql = sql_query
    sql_result = None
    while attempt <= max_retries:
        try:
            sql_result = db_tool.invoke(current_sql)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            attempt += 1
            if attempt > max_retries:
                error_section = (
                    'Error details from the last attempt (do not expose sensitive info):\n'
                    f'{last_error}'
                )
                fallback = FALLBACK_GENERAL_PROMPT_TEMPLATE.format(
                    question=question, error_section=error_section
                )
                resp = llm.invoke(fallback)
                return getattr(resp, 'content', str(resp))

            repair_prompt = SQL_REPAIR_PROMPT_TEMPLATE.format(
                dialect=db.dialect,
                schema=db.get_table_info(),
                question=question,
                sql=current_sql,
                error=last_error,
            )
            fixed = structured_llm.invoke(repair_prompt)
            if isinstance(fixed, dict):
                current_sql = fixed.get('query', current_sql) or current_sql
            else:
                if hasattr(fixed, 'model_dump'):
                    current_sql = (
                        fixed.model_dump().get('query', current_sql) or current_sql
                    )
                else:
                    value = getattr(fixed, 'query', '')
                    if isinstance(value, str) and value.strip():
                        current_sql = value.strip()

    # 3) Answer synthesis
    answer_prompt = ANSWER_SYNTHESIS_TEMPLATE.format(
        question=question, sql_query=current_sql, sql_result=sql_result
    )
    response = llm.invoke(answer_prompt)
    final_text = getattr(response, 'content', str(response)).strip()
    if not final_text:
        fallback = FALLBACK_GENERAL_PROMPT_TEMPLATE.format(
            question=question, error_section=''
        )
        resp = llm.invoke(fallback)
        return getattr(resp, 'content', str(resp))
    return final_text
