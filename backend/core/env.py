from dotenv import load_dotenv
import os

load_dotenv(
    override=True, dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env')
)


class Environment:
    AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
    AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT')


env = Environment()
