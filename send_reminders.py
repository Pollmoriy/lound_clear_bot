"""
Этот скрипт ставится в PythonAnywhere → Tasks → Scheduled tasks, запускать
раз в сутки, например в 10:00. Прокси нужен — скрипт работает на самом
PythonAnywhere и стучится к api.telegram.org.

Команда для Scheduled task (замени путь на свой):
    python3.10 /home/твой_username/loud_clear_bot/send_reminders.py
"""
import asyncio

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, PA_PROXY_URL
from scheduler import check_reminders


async def main():
    session = AiohttpSession(proxy=PA_PROXY_URL) if PA_PROXY_URL else None
    bot = Bot(token=BOT_TOKEN, session=session)
    try:
        await check_reminders(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
