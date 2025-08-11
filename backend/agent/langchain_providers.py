from langchain_openai import AzureChatOpenAI
from core.env import env
from core.app_config import configs
from langchain_community.utilities import SQLDatabase
import os


class Langchain_Providers:
    def __init__(self):
        self.llm = AzureChatOpenAI(
            azure_deployment=env.AZURE_OPENAI_DEPLOYMENT,  # or your deployment
            api_version=env.AZURE_OPENAI_API_VERSION,  # or your api version
            temperature=1,
            api_key=env.AZURE_OPENAI_API_KEY,
            azure_endpoint=env.AZURE_OPENAI_ENDPOINT,
            verbose=True,
        )

        db_path = os.path.join(configs.BASE_PATH, 'data', 'sql', 'custom_db.db')

        self.db = SQLDatabase.from_uri(f'sqlite:///{db_path}')


lc_providers = Langchain_Providers()
