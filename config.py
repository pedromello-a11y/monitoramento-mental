import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
MY_WHATSAPP: str | None = os.environ.get("MY_WHATSAPP")
WHAPI_TOKEN: str | None = os.environ.get("WHAPI_TOKEN")  # legado, não usado
INTERNAL_CRON_SECRET: str | None = os.environ.get("INTERNAL_CRON_SECRET")
OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")
ALLOWED_GROUP_ID: str | None = os.environ.get("ALLOWED_GROUP_ID")
APP_URL: str = os.environ.get("APP_URL", "https://monitoramento-mental-production.up.railway.app")
WA_GATEWAY_URL: str | None = os.environ.get("WA_GATEWAY_URL")
WA_BRIDGE_SECRET: str | None = os.environ.get("WA_BRIDGE_SECRET")
