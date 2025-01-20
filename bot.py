import logging
import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    MenuButtonCommands,
    BotCommand
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web
from dotenv import load_dotenv
import os

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
    WELCOME = "👋 Добро пожаловать! Для доступа подпишитесь на канал:"
    SUBSCRIBE_REQUIRED = "📢 Для продолжения подпишитесь на канал!"
    HELP = """
📚 Помощь:
/start - Перезапустить бота
/menu - Главное меню
/stats - Статистика (для админов)
    """
    MENU = "🏠 Главное меню:"

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

# Клавиатуры
class Keyboards:
    @staticmethod
    def subscription():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
        ])

    @staticmethod
    def main_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Кредитные карты", callback_data="credit")],
            [InlineKeyboardButton(text="💰 Займы", callback_data="loans")],
            [InlineKeyboardButton(text="🛡️ Страхование", callback_data="insurance")],
            [InlineKeyboardButton(text="💼 Работа", callback_data="jobs")],
            [InlineKeyboardButton(text="🎁 Акции", callback_data="promotions")]
        ])

    @staticmethod
    def credit_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧭 Кредитный навигатор", url="https://ppdu.ru/956606fa-02c7-4389-9069-943c0ab8c02b")],
            [InlineKeyboardButton(text="🏦 СберКарта", url="https://trk.ppdu.ru/click/3RujX0b6?erid=2SDnjcVm7Md")],
            [InlineKeyboardButton(text="🏦 Т-Банк Платинум", url="https://trk.ppdu.ru/click/1McwYwsf?erid=2SDnjcyz7NY")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def loans_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 MoneyMan", url="https://trk.ppdu.ru/click/iaxTaZ7u?erid=2SDnjd4NP9c")],
            [InlineKeyboardButton(text="💸 Joymoney", url="https://trk.ppdu.ru/click/1Uf12FL6?erid=Kra23wZmP")],
            [InlineKeyboardButton(text="💸 ДоброЗайм", url="https://trk.ppdu.ru/click/VGWQ7lRU?erid=2SDnjdGSjHa")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def jobs_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚴‍♂️ Яндекс.Еда", url="https://trk.ppdu.ru/click/80UG6A1L?erid=Kra23uVC3")],
            [InlineKeyboardButton(text="🚚 Магнит", url="https://trk.ppdu.ru/click/kUTRwEqg?erid=2SDnjcR2t2N")],
            [InlineKeyboardButton(text="🍔 Burger King", url="https://trk.ppdu.ru/click/UpMcqi2J?erid=2SDnjdu6ZqS")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def insurance_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛡️ ОСАГО", url="https://b2c.pampadu.ru/index.html#2341f23d-fced-49e1-8ecc-2184e809bf77")],
            [InlineKeyboardButton(text="🏠 Ипотека", url="https://ipoteka.pampadu.ru/index.html#c46f5bfd-5d57-41d8-889c-61b8b6860cad")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

    @staticmethod
    def promotions_menu():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Акции", url="https://ppdu.ru/gifts/c94552a5-a5b6-4e65-b191-9b6bc36cd85b")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])

# Мидлварь для логирования
async def log_middleware(handler, event, data):
    logger.info(f"Обработка {event.__class__.__name__} от {event.from_user.id}")
    return await handler(event, data)

# Обработчики
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

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, callback.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await db.update_subscription(callback.from_user.id, True)
            await show_main_menu(callback.message)
        else:
            await callback.answer("❌ Подписка не обнаружена!", show_alert=True)
    except TelegramBadRequest:
        await callback.answer("⚠️ Ошибка проверки подписки!", show_alert=True)

@dp.callback_query(F.data.in_({"credit", "loans", "insurance", "jobs", "promotions"}))
async def handle_category(callback: types.CallbackQuery):
    category = callback.data
    menus = {
        "credit": (Keyboards.credit_menu(), "💳 Кредитные карты:"),
        "loans": (Keyboards.loans_menu(), "💰 Займы и кредиты:"),
        "insurance": (Keyboards.insurance_menu(), "🛡️ Страхование:"),
        "jobs": (Keyboards.jobs_menu(), "💼 Карьерный путь:"),
        "promotions": (Keyboards.promotions_menu(), "🎁 Акции и специальные предложения:")
    }
    keyboard, text = menus[category]
    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(Texts.MENU, reply_markup=Keyboards.main_menu())

async def check_subscription_wrapper(message: types.Message, state: FSMContext):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, message.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await db.update_subscription(message.from_user.id, True)
            await show_main_menu(message)
        else:
            await message.answer(Texts.WELCOME, reply_markup=Keyboards.subscription())
            await state.set_state(Form.check_subscription)
    except TelegramBadRequest:
        await message.answer("⚠️ Ошибка проверки подписки! Попробуйте позже.")

async def show_main_menu(message: types.Message):
    await message.answer(Texts.MENU, reply_markup=Keyboards.main_menu())

# Веб-сервер
async def health_check(request):
    return web.json_response({
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "service": "Telegram Bot"
    })

async def on_startup(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="help", description="Помощь")
    ])

async def main():
    await db.init_db()
    await on_startup(bot)
    
    app = web.Application()
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    
    try:
        await site.start()
        logger.info(f"Сервер запущен на порту {PORT}")
        dp.message.middleware(log_middleware)
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())