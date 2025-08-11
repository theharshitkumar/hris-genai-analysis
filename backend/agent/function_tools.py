import ast
import json
from datetime import datetime

from langchain.tools import Tool

from agent.langchain_providers import lc_providers
from agent.tools_constants import COLUMNS_DESCRIPTIONS

db = lc_providers.db


def run_query_save_results(db, query):
    """
    Runs a query on the specified database and returns the results.

    Args:
        db: The database object to run the query on.
        query: The query to be executed.

    Returns:
        A list containing the results of the query.
    """
    res = db.run(query)
    res = [el for sub in ast.literal_eval(res) for el in sub]
    return res


def get_columns_descriptions(query: str) -> str:
    """
    Useful to get the description of the columns in the rappel_conso_table table.
    """
    return json.dumps(COLUMNS_DESCRIPTIONS)


def get_today_date(query: str) -> str:
    """
    Useful to get the date of today.
    """

    # Getting today's date in string format
    today_date_string = datetime.now().strftime('%Y-%m-%d')
    return today_date_string


def sql_agent_tools():
    tools = [
        Tool.from_function(
            func=get_columns_descriptions,
            name='get_columns_descriptions',
            description="""
            Useful to get the description of the columns in the employees_table table.
            """,
        ),
        Tool.from_function(
            func=get_today_date,
            name='get_today_date',
            description="""
            Useful to get the date of today.
            """,
        ),
    ]
    return tools
