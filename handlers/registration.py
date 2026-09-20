from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database.database import cancel_registration, get_active_events, get_event, register_participant
from utils import format_dt

router = Router()


class RegistrationStates(StatesGroup):
    waiting_for_name = State()


@router.callback_query(F.data.startswith("register:"))
async def start_registration(callback: CallbackQuery, state: FSMContext):
    event_id = int(callback.data.split(":")[1])
    event = await get_event(event_id)
    if not event:
        await callback.answer("Мероприятие не найдено", show_alert=True)
        return

    await state.update_data(event_id=event_id)
    await state.set_state(RegistrationStates.waiting_for_name)
    await callback.message.answer("Как тебя зовут? Напиши имя (и фамилию, если хочешь).")
    await callback.answer()


@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    full_name = message.text.strip()

    event = await get_event(event_id)
    registration, status = await register_participant(
        event_id=event_id,
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name,
    )
    await state.clear()

    if status == "already":
        await message.answer("Ты уже записан(а) на эту встречу 🙂")
        return

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data=f"cancel:{event_id}")]]
    )

    if status == "confirmed":
        text = (
            f"✅ Ты записан(а)!\n\n"
            f"🎉 {event.title}\n"
            f"📅 {format_dt(event.event_datetime)}\n"
            f"📍 {event.location}\n\n"
            f"Передумаешь — жми кнопку ниже."
        )
    else:
        text = (
            f"Свободных мест пока нет, но мы добавили тебя в лист ожидания 📋\n\n"
            f"🎉 {event.title}\n"
            f"Если кто-то отменится — место освободится, и мы тебе напишем."
        )
        cancel_kb.inline_keyboard[0][0].text = "❌ Покинуть лист ожидания"

    await message.answer(text, reply_markup=cancel_kb)


async def cancel_and_notify(bot: Bot, event, user_id: int) -> bool:
    """Cancels user_id's registration for event, notifying anyone promoted
    from the waitlist. Returns True if something was actually cancelled."""
    result = await cancel_registration(event.id, user_id)
    if not result:
        return False
    if result is not True:  # someone was promoted from the waitlist
        try:
            await bot.send_message(
                result.user_id,
                f"🎉 Место освободилось! Ты теперь записан(а) на «{event.title}» ✅",
            )
        except Exception:
            pass
    return True


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    events = await get_active_events()
    cancelled_any = False
    for event in events:
        if await cancel_and_notify(message.bot, event, message.from_user.id):
            cancelled_any = True

    if cancelled_any:
        await message.answer("Регистрация отменена. Спасибо, что предупредил(а)!")
    else:
        await message.answer("Активных регистраций не найдено.")


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_button(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = await get_event(event_id)
    if not event:
        await callback.answer("Мероприятие не найдено", show_alert=True)
        return

    cancelled = await cancel_and_notify(callback.bot, event, callback.from_user.id)
    if cancelled:
        await callback.message.answer(
            "Регистрация отменена. Если передумаешь — просто открой /start снова 🙂"
        )
        await callback.answer()
    else:
        await callback.answer("Активной регистрации не найдено", show_alert=True)
