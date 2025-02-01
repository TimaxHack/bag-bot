import logging
from datetime import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    ConversationHandler,
    filters
)
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SCOPE = ['https://www.googleapis.com/auth/spreadsheets',
         'https://www.googleapis.com/auth/drive']
CREDS = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
CLIENT = gspread.authorize(CREDS)
SHEET_ID = 'YOUR_GOOGLE_SHEET_ID'

DESCRIPTION, STATE, CATEGORY, URGENCY, TIME_SPENT, COMPLEXITY = range(6)

STATES = ['Расписать', 'Ждёт исправления', 'В процессе', 'Исправлен']
CATEGORIES = [
    'Хобби', 'Привычки', 'Навыки', 'Пространство',
    'Время и внимание', 'Страхи и волнения', 'Цель',
    'Идентичность', 'мета', 'Слепые зоны'
]
RATINGS = [str(i) for i in range(1, 11)]

def create_keyboard(items, columns=2):
    keyboard = [items[i:i+columns] for i in range(0, len(items), columns)]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        f"Привет {update.effective_user.first_name}! Я бот для отслеживания багов.\n"
        "Используй /addbug чтобы добавить новый баг",
        reply_markup=ReplyKeyboardRemove()
    )

async def addbug(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Опиши баг:", 
        reply_markup=ReplyKeyboardRemove()
    )
    return DESCRIPTION

async def handle_description(update: Update, context: CallbackContext) -> int:
    context.user_data['bug'] = {'description': update.message.text}
    await update.message.reply_text(
        "Выбери состояние:", 
        reply_markup=create_keyboard(STATES)
    )
    return STATE

async def handle_state(update: Update, context: CallbackContext) -> int:
    context.user_data['bug']['state'] = update.message.text
    await update.message.reply_text(
        "Выбери категорию:", 
        reply_markup=create_keyboard(CATEGORIES, 3)
    )
    return CATEGORY

async def handle_category(update: Update, context: CallbackContext) -> int:
    context.user_data['bug']['category'] = update.message.text
    await update.message.reply_text(
        "Оцени срочность (1-10):", 
        reply_markup=create_keyboard(RATINGS, 5)
    )
    return URGENCY

async def handle_urgency(update: Update, context: CallbackContext) -> int:
    context.user_data['bug']['urgency'] = update.message.text
    await update.message.reply_text(
        "Оцени затраты времени (1-10):", 
        reply_markup=create_keyboard(RATINGS, 5)
    )
    return TIME_SPENT

async def handle_time_spent(update: Update, context: CallbackContext) -> int:
    context.user_data['bug']['time_spent'] = update.message.text
    await update.message.reply_text(
        "Оцени сложность (1-10):", 
        reply_markup=create_keyboard(RATINGS, 5)
    )
    return COMPLEXITY

async def handle_complexity(update: Update, context: CallbackContext) -> int:
    context.user_data['bug']['complexity'] = update.message.text
    
    try:
        sheet = CLIENT.open_by_key(SHEET_ID).sheet1
        row = [
            context.user_data['bug']['description'],
            context.user_data['bug']['state'],
            context.user_data['bug']['category'],
            context.user_data['bug']['urgency'],
            context.user_data['bug']['time_spent'],
            context.user_data['bug']['complexity'],
        ]
        sheet.append_row(row)
        await update.message.reply_text(
            "✅ Баг успешно добавлен!", 
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(
            "❌ Ошибка при добавлении бага", 
            reply_markup=ReplyKeyboardRemove()
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        'Добавление бага отменено', 
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def daily_reminder(context: CallbackContext):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="🕚 23:30! Не забудь добавить сегодняшние баги! /addbug"
    )

def main() -> None:
    application = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('addbug', addbug)],
        states={
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)],
            STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_state)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
            URGENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_urgency)],
            TIME_SPENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_spent)],
            COMPLEXITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_complexity)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        daily_reminder,
        trigger='cron',
        hour=23,
        minute=30,
        kwargs={'context': application}
    )
    scheduler.start()

    application.run_polling()

if __name__ == '__main__':
    main()
