import logging
import asyncio
import aiosqlite
import signal
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from dotenv import load_dotenv
import os
from keyboards import keyboard_manager

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
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
PORT = int(os.getenv("PORT", 5000))

if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в .env")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

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
    HELP = """
📚 Помощь:
/start - Перезапустить бота
/menu - Главное меню
/stats - Статистика (для админов)
/reload - Обновить конфиг (только админ)
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
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await db.add_user(message.from_user.id)
    await show_main_menu(message)

@router.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    await show_main_menu(message)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(Texts.HELP)

@router.message(Command("stats"), AdminFilter(ADMIN_IDS))
async def cmd_stats(message: types.Message):
    total, active = await db.get_stats()
    await message.answer(
        f"📊 Статистика:\n"
        f"Всего пользователей: {total}\n"
        f"Активных подписчиков: {active}"
    )

@router.message(Command("reload"), AdminFilter(ADMIN_IDS))
async def cmd_reload(message: types.Message):
    """Обновление конфигурации клавиатур"""
    try:
        keyboard_manager.reload_config()
        logger.info(f"Админ {message.from_user.id} обновил конфигурацию")
        await message.answer("✅ Конфигурация успешно обновлена!")
    except Exception as e:
        error_msg = f"❌ Ошибка обновления: {str(e)}"
        logger.error(error_msg)
        await message.answer(error_msg)

# Обработчики колбэков
@router.callback_query(F.data.in_({"credit", "loans", "insurance", "jobs", "promotions"}))
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

@router.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        Texts.MENU,
        reply_markup=keyboard_manager.get_markup("main_menu")
    )

# Вспомогательные функции
async def show_main_menu(message: types.Message):
    await message.answer(
        Texts.WELCOME,
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

@router.errors()
async def error_handler(event: types.ErrorEvent):
    logger.error(f"Необработанная ошибка: {event.exception}")
    return True

# Веб-сервер и запуск
async def health_check(request):
    return web.json_response({
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "service": "Telegram Bot"
    })

async def main():
    await bot.delete_webhook()
    await db.init_db()
    
    app = web.Application()
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=PORT)
    await site.start()
    logger.info(f"Сервер запущен на порту {PORT}")
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(shutdown(sig, loop, bot))
        )
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())