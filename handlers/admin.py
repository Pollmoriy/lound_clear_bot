from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMIN_IDS
from database.database import (
    count_registrations,
    create_event,
    deactivate_event,
    get_active_events,
    get_registrations,
    update_capacity,
)
from utils import format_dt

router = Router()


class CreateEventStates(StatesGroup):
    title = State()
    date = State()
    location = State()
    capacity = State()
    photo = State()


class CapacityStates(StatesGroup):
    waiting_for_capacity = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Участники", callback_data=f"admin_participants:{event_id}")],
            [InlineKeyboardButton(text="Лист ожидания", callback_data=f"admin_waitlist:{event_id}")],
            [InlineKeyboardButton(text="Экспорт списка", callback_data=f"admin_export:{event_id}")],
            [InlineKeyboardButton(text="Изменить вместимость", callback_data=f"admin_capacity:{event_id}")],
            [InlineKeyboardButton(text="Закрыть мероприятие", callback_data=f"admin_close:{event_id}")],
        ]
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    events = await get_active_events()
    if not events:
        await message.answer("Активных мероприятий нет. Создай новое: /new_event")
        return

    for event in events:
        confirmed = await count_registrations(event.id, "confirmed")
        waitlist = await count_registrations(event.id, "waitlist")
        text = (
            f"🎉 {event.title} (ID: {event.id})\n"
            f"📅 {format_dt(event.event_datetime)}\n"
            f"👥 {confirmed}/{event.capacity} confirmed\n"
            f"📋 {waitlist} on waitlist"
        )
        await message.answer(text, reply_markup=admin_kb(event.id))


@router.callback_query(F.data.startswith("admin_participants:"))
async def show_participants(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    event_id = int(callback.data.split(":")[1])
    regs = await get_registrations(event_id, "confirmed")
    if not regs:
        text = "Пока никто не записан."
    else:
        text = "👥 Участники:\n" + "\n".join(
            f"{i + 1}. {r.full_name}" + (f" (@{r.username})" if r.username else "")
            for i, r in enumerate(regs)
        )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_waitlist:"))
async def show_waitlist(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    event_id = int(callback.data.split(":")[1])
    regs = await get_registrations(event_id, "waitlist")
    if not regs:
        text = "Лист ожидания пуст."
    else:
        text = "📋 Лист ожидания:\n" + "\n".join(
            f"{i + 1}. {r.full_name}" + (f" (@{r.username})" if r.username else "")
            for i, r in enumerate(regs)
        )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_export:"))
async def export_participants(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    event_id = int(callback.data.split(":")[1])
    confirmed = await get_registrations(event_id, "confirmed")
    waitlist = await get_registrations(event_id, "waitlist")

    lines = ["Статус,Имя,Username"]
    for r in confirmed:
        lines.append(f"confirmed,{r.full_name},{r.username or ''}")
    for r in waitlist:
        lines.append(f"waitlist,{r.full_name},{r.username or ''}")

    csv_bytes = "\n".join(lines).encode("utf-8-sig")  # BOM so Excel shows кириллицу правильно
    file = BufferedInputFile(csv_bytes, filename=f"event_{event_id}_participants.csv")
    await callback.message.answer_document(file)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_capacity:"))
async def ask_capacity(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    event_id = int(callback.data.split(":")[1])
    await state.update_data(event_id=event_id)
    await state.set_state(CapacityStates.waiting_for_capacity)
    await callback.message.answer("Новое количество мест (числом):")
    await callback.answer()


@router.message(CapacityStates.waiting_for_capacity)
async def set_capacity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    try:
        new_cap = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно число, попробуй ещё раз.")
        return
    await update_capacity(data["event_id"], new_cap)
    await state.clear()
    await message.answer(f"Готово, теперь мест: {new_cap}")


@router.callback_query(F.data.startswith("admin_close:"))
async def close_event(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    event_id = int(callback.data.split(":")[1])
    await deactivate_event(event_id)
    await callback.message.answer("Мероприятие закрыто, регистрация на него больше не идёт.")
    await callback.answer()


# --- creating a new event ---

@router.message(Command("new_event"))
async def cmd_new_event(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(CreateEventStates.title)
    await message.answer("Название мероприятия?")


@router.message(CreateEventStates.title)
async def new_event_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(CreateEventStates.date)
    await message.answer("Дата и время в формате ДД.ММ.ГГГГ ЧЧ:ММ (например: 27.09.2026 18:00)")


@router.message(CreateEventStates.date)
async def new_event_date(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("Формат такой: ДД.ММ.ГГГГ ЧЧ:ММ, например 27.09.2026 18:00. Попробуй ещё раз.")
        return
    await state.update_data(event_datetime=dt)
    await state.set_state(CreateEventStates.location)
    await message.answer("Место проведения?")


@router.message(CreateEventStates.location)
async def new_event_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text.strip())
    await state.set_state(CreateEventStates.capacity)
    await message.answer("Сколько мест?")


@router.message(CreateEventStates.capacity)
async def new_event_capacity(message: Message, state: FSMContext):
    try:
        capacity = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно число, попробуй ещё раз.")
        return
    await state.update_data(capacity=capacity)
    await state.set_state(CreateEventStates.photo)
    await message.answer("Пришли фото для мероприятия (или напиши /skip, если без фото).")


async def _finalize_event(message: Message, state: FSMContext, photo_file_id: str | None):
    data = await state.get_data()
    event = await create_event(
        title=data["title"],
        event_datetime=data["event_datetime"],
        location=data["location"],
        capacity=data["capacity"],
        photo_file_id=photo_file_id,
    )
    await state.clear()
    await message.answer(
        f"Мероприятие создано: {event.title} ✅\n"
        f"ID мероприятия: {event.id} (пригодится для ссылки-кнопки в канале)\n"
        f"Теперь оно доступно в /start"
    )


@router.message(CreateEventStates.photo, F.photo)
async def new_event_photo(message: Message, state: FSMContext):
    await _finalize_event(message, state, message.photo[-1].file_id)


@router.message(CreateEventStates.photo, Command("skip"))
async def new_event_skip_photo(message: Message, state: FSMContext):
    await _finalize_event(message, state, None)


@router.message(CreateEventStates.photo)
async def new_event_photo_invalid(message: Message):
    await message.answer("Пришли фото картинкой или напиши /skip")
