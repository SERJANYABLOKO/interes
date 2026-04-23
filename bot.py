# 📁 bot.py
import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext
import events_loader
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN_BOT = os.environ.get("TOKEN_BOT")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Глобальный кеш событий
events_cache = []

# Клавиатура главного меню
def get_main_keyboard():
    buttons = [
        [KeyboardButton("🎲 Мне скучно")],
        [KeyboardButton("🎭 Выбрать категорию")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Клавиатура категорий (inline)
def get_categories_keyboard():
    categories = [
        ("🎵 Концерты", "concert"),
        ("🖼️ Выставки", "exhibition"),
        ("🎬 Кино", "cinema"),
        ("🎭 Театр", "theater"),
        ("📚 Лекции", "lecture"),
        ("⭐ Все категории", "all"),
    ]
    keyboard = []
    for name, callback in categories:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"cat_{callback}")])
    return InlineKeyboardMarkup(keyboard)

# ======================
# Обработчики команд
# ======================

async def start_command(update: Update, context: CallbackContext):
    """Приветствие и главное меню"""
    await update.message.reply_text(
        "🎉 Привет! Я бот «Куда пойти?» в Москве!\n\n"
        "Я помогу тебе найти интересные события на сегодня и ближайшие дни.\n\n"
        "👇 Просто нажми на кнопку «Мне скучно», и я предложу случайное мероприятие!\n"
        "Или выбери категорию, чтобы сузить поиск.",
        reply_markup=get_main_keyboard()
    )
    # Предзагружаем события в фоне
    asyncio.create_task(preload_events())

async def preload_events():
    global events_cache
    events_cache = await events_loader.load_events()
    logger.info(f"Предзагружено {len(events_cache)} событий")

async def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает текстовые сообщения и кнопки"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🎲 Мне скучно":
        await handle_random_event(update, context)
    elif text == "🎭 Выбрать категорию":
        await update.message.reply_text(
            "Выбери категорию события:",
            reply_markup=get_categories_keyboard()
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, используй кнопки меню 👇",
            reply_markup=get_main_keyboard()
        )

async def handle_random_event(update: Update, context: CallbackContext):
    """Отправляет случайное событие"""
    global events_cache
    
    # Если кеш пуст, загружаем события
    if not events_cache:
        await update.message.reply_text("🔍 Загружаю свежие события... Подожди секунду!")
        await preload_events()
    
    if not events_cache:
        await update.message.reply_text(
            "😔 Не удалось загрузить события. Попробуй позже!",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Выбираем случайное событие
    event = events_loader.get_random_event(events_cache)
    if event:
        message = events_loader.format_event_message(event)
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("😔 Не нашлось подходящих событий :(", reply_markup=get_main_keyboard())

async def handle_category_selection(update: Update, context: CallbackContext):
    """Обрабатывает выбор категории (callback query)"""
    query = update.callback_query
    await query.answer()
    
    category_codes = {
        "concert": "concert",
        "exhibition": "exhibition", 
        "cinema": "cinema",
        "theater": "theater",
        "lecture": "lecture",
        "all": None
    }
    
    callback_data = query.data
    category_code = callback_data.replace("cat_", "")
    
    if category_code == "all":
        events = await events_loader.load_events()
        category_name = "все категории"
    else:
        events = await events_loader.load_events([category_code])
        # Находим русское название категории
        category_names = {
            "concert": "концерты",
            "exhibition": "выставки",
            "cinema": "кино",
            "theater": "театр",
            "lecture": "лекции"
        }
        category_name = category_names.get(category_code, "выбранной категории")
    
    if not events:
        await query.edit_message_text(f"😔 Не удалось найти события в категории {category_name}. Попробуй позже!")
        return
    
    await query.edit_message_text(
        f"🎉 Нашел {len(events)} событий в категории {category_name}!\n\n"
        f"Вот одно из них (если хочешь другое, просто нажми «🎲 Мне скучно» снова):",
        reply_markup=None
    )
    
    # Показываем случайное событие из выбранной категории
    event = events_loader.get_random_event(events)
    if event:
        message = events_loader.format_event_message(event)
        await query.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=get_main_keyboard()
        )
    else:
        await query.message.reply_text("😔 Не нашлось событий :(", reply_markup=get_main_keyboard())

# ======================
# Создание приложения
# ======================

def setup_application():
    app = Application.builder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_category_selection, pattern="^cat_"))
    return app

# ======================
# Запуск (как в твоем коде)
# ======================

async def main():
    logger.info("🚀 Запуск бота «Куда пойти?»...")
    
    if not TOKEN_BOT:
        logger.error("❌ TOKEN_BOT не задан")
        return
    
    ptb_app = setup_application()
    await ptb_app.initialize()
    
    # Предзагружаем события в фоне
    asyncio.create_task(preload_events())
    
    if WEBHOOK_URL:
        # Вебхук режим (как в твоем коде)
        from aiohttp import web
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await ptb_app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        logger.info(f"✅ Вебхук установлен: {webhook_url}")
        
        app = web.Application()
        # ... (полный код вебхука как в твоем bot.py)
        logger.info(f"✅ Бот запущен на порту {PORT}")
        await asyncio.Event().wait()
    else:
        await ptb_app.start()
        await ptb_app.updater.start_polling()
        logger.info("✅ Бот запущен в режиме polling")
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
