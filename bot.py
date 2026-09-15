import logging
import os
import sys
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from handlers.game import (
    DATE, TIME, END_TIME, LOC_NAME, LOC_LINK,
    COST, PHONE, NAME, MAX_PLAYERS, PUB_TIME,
    start_form, process_date, process_time, process_end_time,
    process_loc_name, process_loc_link, process_cost, process_phone,
    process_name, process_max_players, process_pub_time, cancel
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

def main():
    if not BOT_TOKEN:
        logging.error("❌ Не задана переменная окружения BOT_TOKEN!")
        return

    # Инициализация приложения python-telegram-bot
    application = Application.builder().token(BOT_TOKEN).build()

    # Настройка пошагового диалога (ConversationHandler)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("newgame", start_form)],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_end_time)],
            LOC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_loc_name)],
            LOC_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_loc_link)],
            COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_cost)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
            MAX_PLAYERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_max_players)],
            PUB_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pub_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    logging.info("==> Бот запущен и готов к работе")
    
    # Запуск бота с очисткой вебхуков
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()