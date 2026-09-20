import ssl
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import DATABASE_URL, DB_SSL_VERIFY
from database.models import Base, Event, Registration

connect_args = {}
if DATABASE_URL.startswith("postgresql"):
    if DB_SSL_VERIFY:
        connect_args["ssl"] = True
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_active_events():
    async with async_session() as session:
        result = await session.execute(
            select(Event).where(Event.is_active == True).order_by(Event.event_datetime)
        )
        return result.scalars().all()


async def get_event(event_id: int):
    async with async_session() as session:
        return await session.get(Event, event_id)


async def count_registrations(event_id: int, status: str) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).select_from(Registration).where(
                Registration.event_id == event_id, Registration.status == status
            )
        )
        return result.scalar_one()


async def create_event(
    title: str,
    event_datetime: datetime,
    location: str,
    capacity: int,
    photo_file_id: str | None = None,
) -> Event:
    async with async_session() as session:
        event = Event(
            title=title,
            event_datetime=event_datetime,
            location=location,
            capacity=capacity,
            photo_file_id=photo_file_id,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event


async def register_participant(event_id: int, user_id: int, username: str | None, full_name: str):
    async with async_session() as session:
        event = await session.get(Event, event_id)
        if event is None:
            return None, "not_found"

        existing = await session.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.user_id == user_id,
                Registration.status.in_(["confirmed", "waitlist"]),
            )
        )
        existing_reg = existing.scalar_one_or_none()
        if existing_reg:
            return existing_reg, "already"

        confirmed_count = (
            await session.execute(
                select(func.count()).select_from(Registration).where(
                    Registration.event_id == event_id, Registration.status == "confirmed"
                )
            )
        ).scalar_one()

        status = "confirmed" if confirmed_count < event.capacity else "waitlist"

        registration = Registration(
            event_id=event_id,
            user_id=user_id,
            username=username,
            full_name=full_name,
            status=status,
        )
        session.add(registration)
        await session.commit()
        await session.refresh(registration)
        return registration, status


async def get_user_registration(event_id: int, user_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.user_id == user_id,
                Registration.status.in_(["confirmed", "waitlist"]),
            )
        )
        return result.scalar_one_or_none()


async def cancel_registration(event_id: int, user_id: int):
    """Cancels a user's registration. If they freed a confirmed spot, promotes
    the first person on the waitlist and returns their Registration object so
    the caller can notify them. Returns True for a plain cancel, False if the
    user had no active registration, or a Registration if someone was promoted.
    """
    async with async_session() as session:
        result = await session.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.user_id == user_id,
                Registration.status.in_(["confirmed", "waitlist"]),
            )
        )
        reg = result.scalar_one_or_none()
        if not reg:
            return False

        was_confirmed = reg.status == "confirmed"
        reg.status = "cancelled"
        await session.commit()

        if was_confirmed:
            wl_result = await session.execute(
                select(Registration)
                .where(Registration.event_id == event_id, Registration.status == "waitlist")
                .order_by(Registration.created_at)
            )
            next_wl = wl_result.scalars().first()
            if next_wl:
                next_wl.status = "confirmed"
                await session.commit()
                await session.refresh(next_wl)
                return next_wl
        return True


async def get_registrations(event_id: int, status: str):
    async with async_session() as session:
        result = await session.execute(
            select(Registration)
            .where(Registration.event_id == event_id, Registration.status == status)
            .order_by(Registration.created_at)
        )
        return result.scalars().all()


async def update_capacity(event_id: int, new_capacity: int):
    async with async_session() as session:
        event = await session.get(Event, event_id)
        if event:
            event.capacity = new_capacity
            await session.commit()
        return event


async def deactivate_event(event_id: int):
    async with async_session() as session:
        event = await session.get(Event, event_id)
        if event:
            event.is_active = False
            await session.commit()
        return event


async def mark_reminder_sent(event_id: int, which: str):
    async with async_session() as session:
        event = await session.get(Event, event_id)
        if not event:
            return
        if which == "24h":
            event.reminder_24h_sent = True
        elif which == "3h":
            event.reminder_3h_sent = True
        await session.commit()
