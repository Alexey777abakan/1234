import logging
import asyncio
import aiosqlite
import signal
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError
from aiohttp import web
from dotenv import load_dotenv
import os
from keyboards import keyboard_manager  # Импорт менеджера клавиатур

# Загрузка переменных окружения
load_dotenv()

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")
ADMIN_IDS = {int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id}
PORT = int(os.getenv("PORT", 5000))

if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в .env")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния FSM
class Form(StatesGroup):
    main_menu = State()
    check_subscription = State()

# Текстовые сообщения
class Texts:
    WELCOME = (
        "👋 Привет! Добро пожаловать в наш бот! 🎉\n\n"
        "Здесь вы можете:\n"
        "💳 Оформить кредит\n"
        "💰 Получить займ\n"
        "🛡️ Оформить страховку\n"
        "💼 Найти работу\n\n"
        "Выберите действие ниже:"
    )
    SUBSCRIBE_REQUIRED = "📢 Для продолжения подпишитесь на канал!"
    HELP = """
📚 Помощь:
/start - Перезапустить бота
/menu - Главное меню
/stats - Статистика (для админов)
    """
    MENU = "🏠 Главное меню:"
    CREDIT_TITLE = "💳 Кредитные карты:"
    LOANS_TITLE = "💰 Займы и кредиты:"
    JOBS_TITLE = "💼 Карьерный путь:"
    INSURANCE_TITLE = "🛡️ Страхование:"
    TREASURE_TITLE = "🎁 Сокровищница выгод:"

# База данных
class Database:
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    subscribed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

    async def add_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user_id,)
            )
            await db.commit()

    async def update_subscription(self, user_id: int, status: bool):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET subscribed = ? WHERE user_id = ?",
                (status, user_id)
            )
            await db.commit()

    async def get_stats(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = await cursor.fetchone()
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE subscribed = TRUE")
            active_users = await cursor.fetchone()
            return total_users[0], active_users[0]

db = Database()

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await db.add_user(message.from_user.id)
    await check_subscription_wrapper(message, state)

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    await show_main_menu(message)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(Texts.HELP)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    total, active = await db.get_stats()
    await message.answer(
        f"📊 Статистика:\n"
        f"Всего пользователей: {total}\n"
        f"Активных подписчиков: {active}"
    )

# Обработчики колбэков
@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await db.update_subscription(callback.from_user.id, True)
            await callback.message.edit_text(
                Texts.WELCOME,
                reply_markup=keyboard_manager.get_markup("main_menu")
            )
        else:
            await callback.answer("❌ Подписка не обнаружена!", show_alert=True)
    except TelegramBadRequest:
        await callback.answer("⚠️ Ошибка проверки подписки!", show_alert=True)

@dp.callback_query(F.data.in_({"credit", "loans", "insurance", "jobs", "promotions"}))
async def handle_category(callback: types.CallbackQuery):
    category = callback.data
    menu_map = {
        "credit": ("credit_menu", Texts.CREDIT_TITLE),
        "loans": ("loans_menu", Texts.LOANS_TITLE),
        "insurance": ("insurance_menu", Texts.INSURANCE_TITLE),
        "jobs": ("jobs_menu", Texts.JOBS_TITLE),
        "promotions": ("promotions_menu", Texts.TREASURE_TITLE)
    }
    
    menu_name, text = menu_map[category]
    await callback.message.edit_text(
        text,
        reply_markup=keyboard_manager.get_markup(menu_name)
    )

@dp.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        Texts.MENU,
        reply_markup=keyboard_manager.get_markup("main_menu")
    )

# Вспомогательные функции
async def check_subscription_wrapper(message: types.Message, state: FSMContext):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, message.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await db.update_subscription(message.from_user.id, True)
            await message.answer(
                Texts.WELCOME,
                reply_markup=keyboard_manager.get_markup("main_menu")
            )
        else:
            await message.answer(
                Texts.SUBSCRIBE_REQUIRED,
                reply_markup=keyboard_manager.get_markup(
                    "subscription",
                    channel_id=CHANNEL_ID[1:]
                )
            )
            await state.set_state(Form.check_subscription)
    except TelegramBadRequest:
        await message.answer("⚠️ Ошибка проверки подписки! Попробуйте позже.")

async def show_main_menu(message: types.Message):
    await message.answer(
        Texts.MENU,
        reply_markup=keyboard_manager.get_markup("main_menu")
    )

# Обработка ошибок
async def shutdown(signal, loop, bot: Bot):
    logger.info("Завершение работы...")
    await bot.session.close()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [t.cancel() for t in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

@dp.error()
async def error_handler(event: types.ErrorEvent):
    if isinstance(event.exception, TelegramConflictError):
        logger.critical("Обнаружен конфликт! Перезапуск через 5 сек...")
        await event.bot.session.close()
        await asyncio.sleep(5)
        await dp.start_polling(event.bot)
    else:
        logger.error(f"Необработанная ошибка: {event.exception}")

# Веб-сервер и запуск
async def health_check(request):
    return web.json_response({
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "service": "Telegram Bot"
    })

async def main():
    # Удаление вебхука перед запуском
    await bot.delete_webhook(drop_pending_updates=True)
    await db.init_db()
    
    # Настройка веб-сервера
    app = web.Application()
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=PORT)
    await site.start()
    logger.info(f"Сервер запущен на порту {PORT}")
    
    # Обработка сигналов
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(shutdown(sig, loop, bot))
        )

    # Запуск бота
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            timeout=60,
            relax=0.1
        )
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()