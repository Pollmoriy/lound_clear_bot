from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.database import count_registrations, get_active_events, get_event, get_user_registration
from utils import format_dt

router = Router()


def events_keyboard(events) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=e.title, callback_data=f"event:{e.id}")] for e in events
        ]
    )


def event_card_text(event, confirmed: int) -> str:
    spots_left = max(event.capacity - confirmed, 0)
    text = (
        f"🎉 {event.title}\n"
        f"📅 {format_dt(event.event_datetime)}\n"
        f"📍 {event.location}\n\n"
        f"👥 {confirmed}/{event.capacity} записано"
    )
    text += f"\n🟢 Осталось мест: {spots_left}" if spots_left > 0 else "\n\n😔 Свободных мест нет"
    return text


def event_card_keyboard(event, spots_left: int, user_status: str | None) -> InlineKeyboardMarkup:
    if user_status:
        label = "❌ Отменить регистрацию" if user_status == "confirmed" else "❌ Покинуть лист ожидания"
        rows = [[InlineKeyboardButton(text=label, callback_data=f"cancel:{event.id}")]]
    else:
        button_text = "🎟 Зарегистрироваться" if spots_left > 0 else "Встать в лист ожидания"
        rows = [[InlineKeyboardButton(text=button_text, callback_data=f"register:{event.id}")]]
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_events")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_event_card(message: Message, event, user_id: int):
    confirmed = await count_registrations(event.id, "confirmed")
    reg = await get_user_registration(event.id, user_id)
    text = event_card_text(event, confirmed)
    kb = event_card_keyboard(event, max(event.capacity - confirmed, 0), reg.status if reg else None)
    if event.photo_file_id:
        await message.answer_photo(event.photo_file_id, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    # deep link from a channel post: t.me/<bot>?start=event_<id>
    if command.args and command.args.startswith("event_"):
        try:
            event_id = int(command.args.split("_", 1)[1])
        except (IndexError, ValueError):
            event_id = None
        if event_id:
            event = await get_event(event_id)
            if event and event.is_active:
                await send_event_card(message, event, message.from_user.id)
                return

    events = await get_active_events()
    if not events:
        await message.answer(
            "Привет! 👋 Пока нет открытых мероприятий — загляни попозже, "
            "скоро объявим первую встречу Loud & Clear."
        )
        return

    await message.answer(
        "Привет! Это бот Loud & Clear для регистрации на встречи 🗣\n\nВыбери мероприятие:",
        reply_markup=events_keyboard(events),
    )


@router.callback_query(F.data.startswith("event:"))
async def show_event(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = await get_event(event_id)
    if not event:
        await callback.answer("Мероприятие не найдено", show_alert=True)
        return

    reg = await get_user_registration(event_id, callback.from_user.id)

    if event.photo_file_id:
        await callback.message.delete()
        await send_event_card(callback.message, event, callback.from_user.id)
    else:
        confirmed = await count_registrations(event_id, "confirmed")
        text = event_card_text(event, confirmed)
        kb = event_card_keyboard(event, max(event.capacity - confirmed, 0), reg.status if reg else None)
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "back_to_events")
async def back_to_events(callback: CallbackQuery):
    events = await get_active_events()
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer("Выбери мероприятие:", reply_markup=events_keyboard(events))
    else:
        await callback.message.edit_text("Выбери мероприятие:", reply_markup=events_keyboard(events))
    await callback.answer()
