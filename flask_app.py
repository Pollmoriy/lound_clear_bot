"""
Точка входа для PythonAnywhere. В отличие от bot.py (long polling, для
локальной разработки), здесь Telegram сам стучится к нам webhook'ом —
это единственный способ работать 24/7 на бесплатном тарифе PythonAnywhere,
у которого нет бесплатного фонового процесса, зато есть бесплатный
постоянно работающий сайт.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from flask import Flask, abort, request

from config import BOT_TOKEN, PA_PROXY_URL, WEBHOOK_SECRET
from database.database import init_db
from handlers import admin, registration, start

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Диспетчер и хранилище FSM — общие на весь процесс, поэтому многошаговые
# сценарии (ввод имени при регистрации, создание мероприятия) работают
# между разными HTTP-запросами так же, как при long polling.
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(start.router)
dp.include_router(registration.router)
dp.include_router(admin.router)

asyncio.run(init_db())


def make_bot() -> Bot:
    # Каждому запросу — свой Bot (и своя aiohttp-сессия), чтобы не привязывать
    # сессию к закрывающемуся после asyncio.run() event loop.
    if PA_PROXY_URL:
        return Bot(token=BOT_TOKEN, session=AiohttpSession(proxy=PA_PROXY_URL))
    return Bot(token=BOT_TOKEN)


@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def telegram_webhook():
    if not WEBHOOK_SECRET:
        abort(403)
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_header != WEBHOOK_SECRET:
        abort(403)

    update = Update.model_validate(request.get_json(force=True))
    bot = make_bot()
    asyncio.run(dp.feed_update(bot, update))
    return "ok"


@app.route("/")
def health():
    return "Loud & Clear bot is alive"
