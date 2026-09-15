from datetime import datetime
import logging
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, ConversationHandler

# Состояния для опросника
(
    DATE, TIME, END_TIME, LOC_NAME, LOC_LINK,
    COST, PHONE, NAME, MAX_PLAYERS, PUB_TIME
) = range(10)

logger = logging.getLogger(__name__)

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()  # Очищаем старые данные перед новым опросом
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
        
        # Копируем накопленные данные игры, чтобы передать их в фоновое задание
        game_data = dict(context.user_data)
        
        # Планируем задачу и передаем в неё данные игры через аргумент data
        context.job_queue.run_once(
            send_scheduled_announcement,
            when=local_dt,
            chat_id=chat_id,
            data=game_data,
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
    data = job.data or {}
    logger.info(f"[Scheduler] Сработал триггер отправки анонса для чата {job.chat_id}")
    
    # Формируем красивый текст анонса из собранных данных
    text = (
        f"🏐 **Волейбольный матч!**\n\n"
        f"📅 **Дата:** {data.get('date', 'Уточняется')}\n"
        f"⏰ **Время:** {data.get('time', '')} - {data.get('end_time', '')}\n"
        f"📍 **Площадка:** {data.get('loc_name', 'Уточняется')}\n"
        f"🗺 [Ссылка на карту]({data.get('loc_link', '#')})\n"
        f"💰 **Стоимость:** {data.get('cost', 'Бесплатно')}\n"
        f"👥 **Максимум игроков:** {data.get('max_players', 'Не указано')}\n"
        f"👤 **Организатор:** {data.get('name', '')} ({data.get('phone', '')})"
    )
    
    # Создаем инлайн-кнопку со ссылкой на ваш GitHub Pages Web App
    web_app_url = "https://flatislove.github.io/SquadGameSignups/"
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏐 Управлять записью", 
                web_app=WebAppInfo(url=web_app_url)
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=job.chat_id, 
        text=text, 
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )