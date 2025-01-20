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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramConflictError
from aiohttp import web
from dotenv import load_dotenv
import os

# Загрузка конфигурации
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

class Config:
    def __init__(self):
        self.API_TOKEN = os.getenv("API_TOKEN")
        self.CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")
        self.ADMIN_IDS = {int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id}
        self.PORT = int(os.getenv("PORT", 5000))
        self.validate()
    
    def validate(self):
        if not self.API_TOKEN:
            raise ValueError("API_TOKEN не найден в .env")

config = Config()

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
    MENU = "🏠 Главное меню:"
    SUBSCRIBE_REQUIRED = "📢 Для продолжения подпишитесь на канал!"
    CREDIT_TITLE = "💳 Кредитные карты:"
    LOANS_TITLE = "💰 Займы и кредиты:"
    JOBS_TITLE = "💼 Карьерный путь:"
    INSURANCE_TITLE = "🛡️ Страхование:"
    TREASURE_TITLE = "🎁 Сокровищница выгод:"
    ERROR = "⚠️ Произошла ошибка. Попробуйте позже."

# Клавиатуры
class Keyboards:
    @staticmethod
    def subscription():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📢 Подписаться на канал", 
                url=f"https://t.me/{config.CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(
                text="✅ Я подписался", 
                callback_data="check_subscription")]
        ])

    @staticmethod
    def main_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Кредитные карты", callback_data="credit"),
             InlineKeyboardButton(text="💰 Займы", callback_data="loans")],
            [InlineKeyboardButton(text="🛡️ Страхование", callback_data="insurance"),
             InlineKeyboardButton(text="💼 Работа", callback_data="jobs")],
            [InlineKeyboardButton(text="🎁 Сокровищница выгод", callback_data="treasure")]
        ])

    @staticmethod
    def credit_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧭 Кредитный навигатор", url="https://ppdu.ru/956606fa-02c7-4389-9069-943c0ab8c02b")],
            [InlineKeyboardButton(text="🏦 СберБанк - Кредитная СберКарта", url="https://trk.ppdu.ru/click/3RujX0b6?erid=2SDnjcVm7Md")],
            [InlineKeyboardButton(text="🏦 Т-Банк - Кредитная карта Платинум", url="https://trk.ppdu.ru/click/1McwYwsf?erid=2SDnjcyz7NY")],
            [InlineKeyboardButton(text="🏦 Уралсиб - Кредитная карта с кешбэком", url="https://trk.ppdu.ru/click/bhA4OaNe?erid=2SDnje5iw3n")],
            [InlineKeyboardButton(text="🏦 Т-Банк — Кешбэк 2 000 рублей", url="https://trk.ppdu.ru/click/QYJQHNtB?erid=2SDnjdSG9a1")],
            [InlineKeyboardButton(text="🏦 Совкомбанк - Халва МИР", url="https://trk.ppdu.ru/click/8lDSWnJn?erid=Kra23XHz1")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def loans_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Займ-Мастер", url="https://ppdu.ru/8bfd124d-1628-4eb2-a238-531a4c629329")],
            [InlineKeyboardButton(text="💸 MoneyMan", url="https://trk.ppdu.ru/click/iaxTaZ7u?erid=2SDnjd4NP9c")],
            [InlineKeyboardButton(text="💸 Joymoney", url="https://trk.ppdu.ru/click/1Uf12FL6?erid=Kra23wZmP")],
            [InlineKeyboardButton(text="💸 Целевые финансы", url="https://trk.ppdu.ru/click/uqh4iG8P?erid=2SDnjeePynH")],
            [InlineKeyboardButton(text="💸 ДоброЗайм", url="https://trk.ppdu.ru/click/VGWQ7lRU?erid=2SDnjdGSjHa")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def jobs_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💼 Карьерный навигатор", url="https://ppdu.ru/c8f23f85-45da-4804-a190-e6a358a9061b")],
            [InlineKeyboardButton(text="🚴‍♂️ Яндекс.Еда/Лавка", url="https://trk.ppdu.ru/click/80UG6A1L?erid=Kra23uVC3")],
            [InlineKeyboardButton(text="🚚 Магнит (Кат. Е)", url="https://trk.ppdu.ru/click/kUTRwEqg?erid=2SDnjcR2t2N")],
            [InlineKeyboardButton(text="🍔 Burger King", url="https://trk.ppdu.ru/click/UpMcqi2J?erid=2SDnjdu6ZqS")],
            [InlineKeyboardButton(text="🏦 Альфа Банк", url="https://trk.ppdu.ru/click/Sg02KcAS?erid=2SDnjbsvvT3")],
            [InlineKeyboardButton(text="🏦 Т-Банк — Работа", url="https://trk.ppdu.ru/click/JdRx49qY?erid=2SDnjcbs16H")],
            [InlineKeyboardButton(text="📱 МТС Продажи", url="https://trk.ppdu.ru/click/8Vv8AUVS?erid=2SDnjdhc8em")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def insurance_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛡️ ОСАГО", url="https://b2c.pampadu.ru/index.html#2341f23d-fced-49e1-8ecc-2184e809bf77")],
            [InlineKeyboardButton(text="🏠 Страхование ипотеки", url="https://ipoteka.pampadu.ru/index.html#c46f5bfd-5d57-41d8-889c-61b8b6860cad")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def treasure_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Сокровищница выгод", url="https://ppdu.ru/gifts/c94552a5-a5b6-4e65-b191-9b6bc36cd85b")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

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
                )''')
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

# Инициализация бота и БД
bot = Bot(token=config.API_TOKEN)
dp = Dispatcher()
db = Database()

# Обработчики ошибок
async def shutdown(signal, loop, bot: Bot):
    logger.info("Завершение работы...")
    await bot.session.close()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [t.cancel() for t in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

@dp.errors(exception=TelegramConflictError)
async def handle_conflict_error(event: ErrorEvent):
    logger.critical("Обнаружен конфликт! Перезапуск бота...")
    await asyncio.sleep(5)
    await dp.start_polling(bot)

# Основные обработчики
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        await db.add_user(message.from_user.id)
        
        if not await check_subscription(message.from_user.id):
            await message.answer(
                Texts.SUBSCRIBE_REQUIRED,
                reply_markup=Keyboards.subscription()
            )
            await state.set_state(Form.check_subscription)
            return

        await message.answer(Texts.WELCOME, reply_markup=Keyboards.main_menu())
        await state.set_state(Form.main_menu)
        
    except Exception as e:
        logger.error(f"Ошибка в /start: {str(e)}")
        await message.answer(Texts.ERROR)

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        if await check_subscription(callback.from_user.id):
            await callback.message.edit_text(
                Texts.WELCOME,
                reply_markup=Keyboards.main_menu()
            )
            await state.set_state(Form.main_menu)
        else:
            await callback.answer("❌ Вы ещё не подписались!", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {str(e)}")
        await callback.answer(Texts.ERROR)

@dp.callback_query(F.data.in_({"credit", "loans", "insurance", "jobs", "treasure"}))
async def menu_handler(callback: types.CallbackQuery):
    try:
        menu_map = {
            "credit": (Keyboards.credit_menu(), Texts.CREDIT_TITLE),
            "loans": (Keyboards.loans_menu(), Texts.LOANS_TITLE),
            "insurance": (Keyboards.insurance_menu(), Texts.INSURANCE_TITLE),
            "jobs": (Keyboards.jobs_menu(), Texts.JOBS_TITLE),
            "treasure": (Keyboards.treasure_menu(), Texts.TREASURE_TITLE)
        }
        keyboard, text = menu_map[callback.data]
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка меню: {str(e)}")
        await callback.answer(Texts.ERROR)

@dp.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_text(
            Texts.MENU,
            reply_markup=Keyboards.main_menu()
        )
        await state.set_state(Form.main_menu)
    except Exception as e:
        logger.error(f"Ошибка возврата: {str(e)}")
        await callback.answer(Texts.ERROR)

# Вспомогательные функции
async def check_subscription(user_id: int):
    try:
        member = await bot.get_chat_member(config.CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {str(e)}")
        return False

# Запуск приложения
async def main():
    await db.init_db()
    
    # Настройка веб-сервера для health checks
    app = web.Application()
    app.router.add_get("/ping", lambda request: web.Response(text="pong"))
    
    # Обработка сигналов
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(shutdown(sig, loop, bot))
        )

    # Запуск поллинга с защитой от конфликтов
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                timeout=60,
                relax=0.1
            )
            break
        except TelegramConflictError:
            if attempt < max_retries - 1:
                logger.warning(f"Конфликт! Повторная попытка через {retry_delay} сек...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("Не удалось запустить бота из-за конфликта")
                sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())