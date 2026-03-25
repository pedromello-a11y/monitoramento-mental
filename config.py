import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
MY_WHATSAPP: str | None = os.environ.get("MY_WHATSAPP")
WHAPI_TOKEN: str | None = os.environ.get("WHAPI_TOKEN")
INTERNAL_CRON_SECRET: str | None = os.environ.get("INTERNAL_CRON_SECRET")
OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
