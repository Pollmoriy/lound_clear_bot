import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///loud_clear.db")
PORT = int(os.getenv("PORT", "10000"))  # used only by the local polling bot.py, not by PythonAnywhere

# --- webhook / PythonAnywhere ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PA_USERNAME = os.getenv("PA_USERNAME", "")
WEBHOOK_URL = (
    f"https://{PA_USERNAME}.pythonanywhere.com/webhook/{WEBHOOK_SECRET}"
    if PA_USERNAME and WEBHOOK_SECRET
    else ""
)
# PythonAnywhere free tier requires routing outbound requests through their proxy.
# Leave empty for local runs; set to http://proxy.server:3128 in PythonAnywhere's .env
PA_PROXY_URL = os.getenv("PA_PROXY_URL", "")
DB_SSL_VERIFY = os.getenv("DB_SSL_VERIFY", "true").lower() != "false"
