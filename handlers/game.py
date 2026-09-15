from datetime import datetime
import logging
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# Состояния для опросника
(
    DATE, TIME, END_TIME, LOC_NAME, LOC_LINK,
    COST, PHONE, NAME, MAX_PLAYERS, PUB_TIME
) = range(10)

logger = logging.getLogger(__name__)

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите дату игры (например, 20.09.2026):")
    return DATE

async def process_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['date'] = update.message.text
    await update.message.reply_text("Введите время начала (например, 19:00):")
    return TIME

async def process_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['time'] = update.message.text
    await update.message.reply_text("Введите время окончания:")
    return END_TIME

async def process_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['end_time'] = update.message.text
    await update.message.reply_text("Введите название площадки:")
    return LOC_NAME

async def process_loc_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['loc_name'] = update.message.text
    await update.message.reply_text("Введите ссылку на карту:")
    return LOC_LINK

async def process_loc_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['loc_link'] = update.message.text
    await update.message.reply_text("Введите стоимость:")
    return COST

async def process_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['cost'] = update.message.text
    await update.message.reply_text("Введите телефон для связи:")
    return PHONE

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Введите имя организатора:")
    return NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Введите максимальное количество игроков:")
    return MAX_PLAYERS

async def process_max_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['max_players'] = update.message.text
    await update.message.reply_text("Введите время публикации анонса (в формате ДД.ММ.ГГГГ ЧЧ:ММ):")
    return PUB_TIME

async def process_pub_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pub_time_str = update.message.text
    chat_id = update.effective_chat.id
    logger.info(f"[Form] Получено время публикации: {pub_time_str}")
    
    try:
        local_tz = ZoneInfo('Asia/Almaty')
        local_dt = datetime.strptime(pub_time_str, "%d.%m.%Y %H:%M").replace(tzinfo=local_tz)
        
        # Используем встроенный в PTB планировщик (JobQueue)
        context.job_queue.run_once(
            send_scheduled_announcement,
            when=local_dt,
            chat_id=chat_id,
            name=str(chat_id)
        )
        
        await update.message.reply_text("✅ Игра сохранена и анонс успешно запланирован!")
        logger.info(f"[Scheduler] Задача успешно запланирована на {local_dt}")
        
    except Exception as e:
        logger.error(f"[Scheduler Error] Ошибка планирования: {e}")
        await update.message.reply_text("❌ Неверный формат даты/времени. Попробуйте заново через /newgame")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Создание игры отменено.")
    return ConversationHandler.END

async def send_scheduled_announcement(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    logger.info(f"[Scheduler] Сработал триггер отправки анонса для чата {job.chat_id}")
    await context.bot.send_message(chat_id=job.chat_id, text="📢 Внимание! Анонс запланированной игры.")