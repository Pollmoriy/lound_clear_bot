"""
Запускается ОДИН РАЗ с твоего компьютера (не на PythonAnywhere), чтобы
сказать Telegram: "присылай обновления сюда". Прокси не нужен — это
обычный запрос с твоего локального интернета.
"""
import asyncio

from aiogram import Bot

from config import BOT_TOKEN, WEBHOOK_SECRET, WEBHOOK_URL


async def main():
    if not WEBHOOK_URL:
        raise RuntimeError(
            "Добавь в .env свои PA_USERNAME и WEBHOOK_SECRET — "
            "webhook URL собирается из них автоматически (см. README)."
        )
    bot = Bot(token=BOT_TOKEN)
    await bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET, drop_pending_updates=True)
    print("Webhook установлен на:", WEBHOOK_URL)
    print(await bot.get_webhook_info())
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
