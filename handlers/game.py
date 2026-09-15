import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Глобальное хранилище активных игр (используется bot.py для API эндпоинтов и записи)
ACTIVE_GAMES = {}

async def send_scheduled_announcement(context: ContextTypes.DEFAULT_TYPE):
    """Фоновая задача для отправки отложенного анонса матча."""
    job = context.job
    data = job.data or {}
    logger.info(f"[Scheduler] Сработал триггер отправки анонса для чата {job.chat_id}")
    
    # Формируем красивый текст анонса из данных, пришедших из веб-формы
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
    
    # Ссылка на ваш Web App на GitHub Pages или Render
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
    
    try:
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text=text, 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"[Scheduler Error] Не удалось отправить анонс в чат {job.chat_id}: {e}")