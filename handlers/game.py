from datetime import datetime
import logging
from zoneinfo import ZoneInfo
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from states import NewGameForm

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "/newgame")
async def start_form(message: Message, state: FSMContext):
    await state.set_state(NewGameForm.date)
    await message.answer("Введите дату игры (например, 20.09.2026):")

@router.message(NewGameForm.date)
async def process_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(NewGameForm.time)
    await message.answer("Введите время начала (например, 19:00):")

@router.message(NewGameForm.time)
async def process_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await state.set_state(NewGameForm.end_time)
    await message.answer("Введите время окончания:")

@router.message(NewGameForm.end_time)
async def process_end_time(message: Message, state: FSMContext):
    await state.update_data(end_time=message.text)
    await state.set_state(NewGameForm.loc_name)
    await message.answer("Введите название площадки:")

@router.message(NewGameForm.loc_name)
async def process_loc_name(message: Message, state: FSMContext):
    await state.update_data(loc_name=message.text)
    await state.set_state(NewGameForm.loc_link)
    await message.answer("Введите ссылку на карту:")

@router.message(NewGameForm.loc_link)
async def process_loc_link(message: Message, state: FSMContext):
    await state.update_data(loc_link=message.text)
    await state.set_state(NewGameForm.cost)
    await message.answer("Введите стоимость:")

@router.message(NewGameForm.cost)
async def process_cost(message: Message, state: FSMContext):
    await state.update_data(cost=message.text)
    await state.set_state(NewGameForm.phone)
    await message.answer("Введите телефон для связи:")

@router.message(NewGameForm.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(NewGameForm.name)
    await message.answer("Введите имя организатора:")

@router.message(NewGameForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(NewGameForm.max_players)
    await message.answer("Введите максимальное количество игроков:")

@router.message(NewGameForm.max_players)
async def process_max_players(message: Message, state: FSMContext):
    await state.update_data(max_players=message.text)
    await state.set_state(NewGameForm.pub_time)
    await message.answer("Введите время публикации анонса (в формате ДД.ММ.ГГГГ ЧЧ:ММ):")

@router.message(NewGameForm.pub_time)
async def process_pub_time(message: Message, state: FSMContext, scheduler: AsyncIOScheduler):
    pub_time_str = message.text
    logger.info(f"[Form] Получено время публикации: {pub_time_str}")
    
    try:
        local_tz = ZoneInfo('Asia/Almaty')
        local_dt = datetime.strptime(pub_time_str, "%d.%m.%Y %H:%M").replace(tzinfo=local_tz)
        utc_dt = local_dt.astimezone(ZoneInfo('UTC'))
        
        scheduler.add_job(
            send_scheduled_announcement,
            'date',
            run_date=utc_dt,
            args=[message.chat.id]
        )
        
        await message.answer("✅ Игра сохранена и анонс успешно запланирован!")
        logger.info(f"[Scheduler] Задача успешно запланирована на {utc_dt} (UTC)")
        
    except Exception as e:
        logger.error(f"[Scheduler Error] Ошибка планирования: {e}")
        await message.answer("❌ Неверный формат даты/времени. Попробуйте еще раз в формате ДД.ММ.ГГГГ ЧЧ:ММ")
        return

    # ВАЖНО: всегда очищаем стейт в конце
    await state.clear()

async def send_scheduled_announcement(chat_id: int):
    logger.info(f"[Scheduler] Сработал триггер отправки анонса для чата {chat_id}")