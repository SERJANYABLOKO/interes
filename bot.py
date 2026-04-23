# 📁 bot.py (с отладкой)
import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext
from aiohttp import web
import events_loader

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
    logger.info(f"📱 Пользователь {update.effective_user.id} вызвал /start")
    await update.message.reply_text(
        "🎉 Привет! Я бот «Куда пойти?» в Москве!\n\n"
        "Я помогу тебе найти интересные события на сегодня и ближайшие дни.\n\n"
        "👇 Просто нажми на кнопку «Мне скучно», и я предложу случайное мероприятие!\n"
        "Или выбери категорию, чтобы сузить поиск.",
        reply_markup=get_main_keyboard()
    )

async def preload_events():
    global events_cache
    logger.info("🔄 Начинаю загрузку событий...")
    events_cache = await events_loader.load_events()
    logger.info(f"✅ Загружено {len(events_cache)} событий в кеш")
    if len(events_cache) > 0:
        # Выводим пример первого события для проверки
        sample = events_cache[0]
        logger.info(f"📋 Пример события: {sample.get('title', 'Нет названия')}")

async def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает текстовые сообщения и кнопки"""
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"📨 Получено сообщение от {user_id}: {text}")
    
    if text == "🎲 Мне скучно":
        logger.info(f"🎲 Пользователь {user_id} нажал «Мне скучно»")
        await handle_random_event(update, context)
    elif text == "🎭 Выбрать категорию":
        logger.info(f"🎭 Пользователь {user_id} выбрал категории")
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
    user_id = update.effective_user.id
    
    logger.info(f"🔍 Обработка случайного события для {user_id}")
    logger.info(f"📊 Размер кеша: {len(events_cache)}")
    
    # Если кеш пуст, загружаем события
    if not events_cache:
        logger.warning("⚠️ Кеш пуст, загружаю события...")
        await update.message.reply_text("🔍 Загружаю свежие события... Подожди секунду!")
        await preload_events()
    
    if not events_cache:
        logger.error("❌ Кеш остался пустым после загрузки")
        await update.message.reply_text(
            "😔 Не удалось загрузить события. Попробуй позже!\n\n"
            "Возможные причины:\n"
            "- Нет интернета\n"
            "- API KudaGo временно недоступен\n"
            "- Попробуй через минуту",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Выбираем случайное событие
    event = events_loader.get_random_event(events_cache)
    if event:
        logger.info(f"✅ Найдено событие: {event.get('title', 'Без названия')}")
        message = events_loader.format_event_message(event)
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True,
            reply_markup=get_main_keyboard()
        )
    else:
        logger.error("❌ Не удалось получить случайное событие из кеша")
        await update.message.reply_text(
            "😔 Не нашлось подходящих событий :(\n"
            "Попробуй выбрать категорию или нажми позже",
            reply_markup=get_main_keyboard()
        )

async def handle_category_selection(update: Update, context: CallbackContext):
    """Обрабатывает выбор категории (callback query)"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    callback_data = query.data
    category_code = callback_data.replace("cat_", "")
    logger.info(f"📂 Пользователь {user_id} выбрал категорию: {category_code}")
    
    if category_code == "all":
        events = await events_loader.load_events()
        category_name = "все категории"
    else:
        events = await events_loader.load_events([category_code])
        category_names = {
            "concert": "концерты",
            "exhibition": "выставки",
            "cinema": "кино",
            "theater": "театр",
            "lecture": "лекции"
        }
        category_name = category_names.get(category_code, "выбранной категории")
    
    logger.info(f"📊 Найдено {len(events)} событий в категории {category_name}")
    
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
# Webhook обработчики для aiohttp
# ======================

async def webhook_handler(request):
    """Обработчик вебхуков от Telegram"""
    try:
        data = await request.json()
        
        # Получаем приложение из контекста
        bot_app = request.app['bot_app']
        
        # Создаем update объект
        update = Update.de_json(data, bot_app.bot)
        
        # Обрабатываем обновление
        await bot_app.process_update(update)
        
        logger.info("✅ Webhook обработан")
        return web.Response(text="OK", status=200)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook: {e}")
        return web.Response(text="Error", status=500)

async def health_handler(request):
    """Health check handler"""
    return web.Response(text="OK", status=200)

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
# Запуск
# ======================

async def main():
    logger.info("🚀 Запуск бота «Куда пойти?»...")
    
    if not TOKEN_BOT:
        logger.error("❌ TOKEN_BOT не задан")
        return
    
    # Создаем приложение Telegram
    ptb_app = setup_application()
    await ptb_app.initialize()
    
    # Предзагружаем события в фоне
    asyncio.create_task(preload_events())
    
    if WEBHOOK_URL:
        logger.info(f"🌐 Режим вебхука на порту {PORT}")
        
        # Устанавливаем вебхук
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = await ptb_app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        
        if result:
            logger.info(f"✅ Вебхук успешно установлен: {webhook_url}")
        else:
            logger.error("❌ Не удалось установить вебхук")
            return
        
        # Настраиваем aiohttp сервер
        app = web.Application()
        app['bot_app'] = ptb_app
        app.router.add_post('/webhook', webhook_handler)
        app.router.add_get('/health', health_handler)
        app.router.add_get('/', health_handler)
        
        # Запускаем сервер
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        
        logger.info(f"✅ Бот запущен на порту {PORT}")
        logger.info(f"✅ Webhook URL: {webhook_url}")
        
        # Держим сервер запущенным
        await asyncio.Event().wait()
        
    else:
        logger.warning("⚠️ WEBHOOK_URL не указан, используем polling")
        # Запускаем polling
        await ptb_app.start()
        await ptb_app.updater.start_polling()
        logger.info("✅ Бот запущен в режиме polling")
        
        # Держим бота запущенным
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
