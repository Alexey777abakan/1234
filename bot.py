import os
import re
import signal
import logging
import asyncio
import aiosqlite
from contextlib import suppress
from datetime import datetime
from typing import Optional, Dict, List

from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация приложения
class Config:
    """Конфигурация приложения, загружаемая из переменных окружения"""
    
    def __init__(self):
        self.API_TOKEN = os.getenv("API_TOKEN")
        self.CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")
        self.ADMIN_IDS = {int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id}
        self.REDIS_URL = os.getenv("REDIS_URL")
        self.PORT = int(os.getenv("PORT", 8080))
        self.validate()

    def validate(self):
        """Проверка корректности конфигурации"""
        if not self.API_TOKEN:
            raise ValueError("API_TOKEN не найден в .env")
        if not self.CHANNEL_ID.startswith("@"):
            raise ValueError("CHANNEL_ID должен начинаться с @")

config = Config()

# Состояния конечного автомата
class Form(StatesGroup):
    menu = State()
    phone_input = State()

# Текстовые сообщения
class Texts:
    WELCOME = (
        "👋 Добро пожаловать в финансового помощника! 🎉\n\n"
        "Выберите нужную категорию:"
    )
    MENU = "Главное меню:"
    PHONE_REQUEST = "📱 Пожалуйста, поделитесь вашим номером телефона:"
    PHONE_INVALID = "❌ Неверный формат номера. Используйте +7XXXXXXXXXX"
    SUBSCRIBE_REQUIRED = "📢 Для продолжения подпишитесь на наш канал!"
    ERROR = "⚠️ Произошла ошибка. Попробуйте позже."
    ADMIN_HELP = "Админ-команды:\n/broadcast - Рассылка\n/stats - Статистика"

# Фабрика клавиатур
class KeyboardFactory:
    """Фабрика для создания интерактивных клавиатур"""
    
    @staticmethod
    def create_menu() -> InlineKeyboardMarkup:
        """Создает основное меню"""
        items = [
            ("💳 Кредитные карты", "credit_cards"),
            ("💰 Займы", "loans"),
            ("🛡️ Страхование", "insurance"),
            ("💼 Работа", "jobs"),
            ("🎁 Акции", "promotions")
        ]
        return KeyboardFactory._create_keyboard(items)

    @staticmethod
    def _create_keyboard(items: List[tuple], back: bool = True) -> InlineKeyboardMarkup:
        """Внутренний метод для создания клавиатуры"""
        buttons = [
            [InlineKeyboardButton(text=text, callback_data=data)]
            for text, data in items
        ]
        if back:
            buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

# Репозиторий для работы с базой данных
class UserRepository:
    """Класс для работы с пользовательскими данными"""
    
    def __init__(self, db_path: str = "users.db"):
        self.db_path = db_path
        self.cache = {}

    async def initialize(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA synchronous=NORMAL')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    phone TEXT CHECK(length(phone) BETWEEN 12 AND 20),
                    subscribed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) STRICT
            ''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя из кэша или БД"""
        if user_id in self.cache:
            return self.cache[user_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    user = dict(row)
                    self.cache[user_id] = user
                    return user
                return None

    async def update_phone(self, user_id: int, phone: str):
        """Обновление номера телефона пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, phone) VALUES (?, ?)",
                (user_id, phone)
            )
            await db.commit()
        if user_id in self.cache:
            self.cache[user_id]['phone'] = phone

# Обработчик ошибок
class EnhancedErrorHandler:
    """Класс для обработки и логирования ошибок"""
    
    @staticmethod
    async def handle_error(message: Message, error: Exception, context: str):
        logger.error(f"Error in {context}: {str(error)}", exc_info=True)
        await message.answer(Texts.ERROR)

# Инициализация основных компонентов
bot = Bot(token=config.API_TOKEN)
storage = RedisStorage.from_url(config.REDIS_URL) if config.REDIS_URL else MemoryStorage()
dp = Dispatcher(storage=storage)
user_repo = UserRepository()

# Мидлварь для логирования
class LoggingMiddleware:
    async def __call__(self, handler, event, data):
        logger.info(f"Обработка события: {event}")
        try:
            return await handler(event, data)
        except Exception as e:
            await EnhancedErrorHandler.handle_error(event, e, "middleware")
            raise

dp.update.middleware.register(LoggingMiddleware())

# Хендлеры команд
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    try:
        if not await check_subscription(message.from_user.id):
            await message.answer(Texts.SUBSCRIBE_REQUIRED)
            return

        user = await user_repo.get_user(message.from_user.id)
        text = Texts.WELCOME if not user else "👋 С возвращением!"
        
        await message.answer(
            text,
            reply_markup=KeyboardFactory.create_menu()
        )
        await state.set_state(Form.menu)
        
    except Exception as e:
        await EnhancedErrorHandler.handle_error(message, e, "cmd_start")

@dp.callback_query(lambda c: c.data == "back")
async def back_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад'"""
    try:
        await callback.message.edit_text(
            Texts.MENU,
            reply_markup=KeyboardFactory.create_menu()
        )
        await state.set_state(Form.menu)
    except Exception as e:
        await EnhancedErrorHandler.handle_error(callback.message, e, "back_handler")

# Вспомогательные функции
async def check_subscription(user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

# Управление жизненным циклом
async def shutdown(dispatcher: Dispatcher, bot: Bot, app: web.Application):
    """Корректное завершение работы"""
    logger.info("Завершение работы...")
    await dispatcher.storage.close()
    await bot.session.close()
    await app.shutdown()

def handle_signal(signum, loop, dp: Dispatcher, bot: Bot, app: web.Application):
    """Обработчик системных сигналов"""
    logger.warning(f"Получен сигнал {signum}")
    loop.create_task(shutdown(dp, bot, app))

# Веб-сервер и healthcheck
async def health_check(request):
    """Проверка работоспособности сервиса"""
    return web.json_response({
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "database": "active",
        "cache_size": len(user_repo.cache)
    })

async def main():
    """Основная функция запуска"""
    await user_repo.initialize()
    
    app = web.Application()
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    
    loop = asyncio.get_event_loop()
    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(
            getattr(signal, signame),
            lambda: handle_signal(signame, loop, dp, bot, app)
        )

    try:
        await site.start()
        logger.info(f"Сервер запущен на порту {config.PORT}")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Работа завершена")