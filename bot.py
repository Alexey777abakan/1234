import logging
import asyncio
import aiosqlite
import signal
import os
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from dotenv import load_dotenv
import aiohttp
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Создаем папку logs, если её нет
if not os.path.exists("logs"):
    os.makedirs("logs")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
PORT = int(os.getenv("PORT", 10000))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///users.db")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-3.5-sonnet")
CLAUDE_API_URL = os.getenv("CLAUDE_API_URL", "https://proxy.tune.app/chat/completions")

if not API_TOKEN or not CLAUDE_API_KEY:
    raise ValueError("Отсутствует API_TOKEN или CLAUDE_API_KEY в .env")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Состояния FSM
class Form(StatesGroup):
    ask_neuro = State()

# База данных
class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_URL

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    subscribed BOOLEAN DEFAULT FALSE,
                    questions_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()

    async def add_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def increment_question_count(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET questions_count = questions_count + 1 WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_question_count(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT questions_count FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0

db = Database()

# Проверка подписки пользователя на канал
async def is_user_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# Обработчик команды /start
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await db.add_user(message.from_user.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Кредитные предложения", callback_data="credit")],
        [InlineKeyboardButton(text="🤖 Спросить нейросеть", callback_data="ask_neuro")]
    ])
    await message.answer("👋 Привет! Выберите действие:", reply_markup=keyboard)

# Обработчик кнопки "Кредитные предложения"
@router.callback_query(lambda c: c.data == "credit")
async def credit_offers(callback: types.CallbackQuery):
    await callback.message.answer("💳 Вот наши лучшие кредитные предложения: ...")

# Обработчик кнопки "Спросить нейросеть"
@router.callback_query(lambda c: c.data == "ask_neuro")
async def ask_neuro_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS

    if is_admin or await is_user_subscribed(user_id):
        await callback.message.answer("Введите ваш вопрос:")
        await state.set_state(Form.ask_neuro)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID[1:]}")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
        ])
        await callback.message.answer("📢 Подпишитесь на канал, чтобы задать вопрос:", reply_markup=keyboard)

# Проверка подписки
@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    if await is_user_subscribed(callback.from_user.id):
        await callback.message.answer("✅ Спасибо за подписку! Теперь можете задать вопрос.")
        await state.set_state(Form.ask_neuro)
    else:
        await callback.answer("❌ Вы ещё не подписаны. Подпишитесь и попробуйте снова.", show_alert=True)

# Запуск в режиме webhook
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await db.init_db()
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=PORT).start()
    await bot.set_webhook("https://my-telegram-bot-yb0n.onrender.com/webhook")

if __name__ == "__main__":
    asyncio.run(main())
