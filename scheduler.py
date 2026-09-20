import logging
from datetime import datetime, timedelta

from aiogram import Bot

from database.database import get_active_events, get_registrations, mark_reminder_sent
from utils import format_dt

logger = logging.getLogger(__name__)


async def check_reminders(bot: Bot):
    """Рассчитан на запуск примерно раз в сутки (PythonAnywhere Scheduled
    Task на бесплатном тарифе позволяет ровно это). Шлёт одно напоминание
    всем подтверждённым участникам мероприятия, если до него осталось
    меньше 48 часов и напоминание ещё не отправлялось."""
    now = datetime.now()
    events = await get_active_events()

    for event in events:
        time_left = event.event_datetime - now
        if timedelta(0) < time_left <= timedelta(hours=48) and not event.reminder_24h_sent:
            await _send_reminder(bot, event)
            await mark_reminder_sent(event.id, "24h")


async def _send_reminder(bot: Bot, event):
    confirmed = await get_registrations(event.id, "confirmed")
    text = (
        f"⏰ Напоминаем про встречу совсем скоро!\n\n"
        f"🎉 {event.title}\n"
        f"📅 {format_dt(event.event_datetime)}\n"
        f"📍 {event.location}\n\n"
        f"Если планы поменялись — напиши /cancel."
    )
    for reg in confirmed:
        try:
            await bot.send_message(reg.user_id, text)
        except Exception:
            logger.exception("Failed to send reminder to %s", reg.user_id)
