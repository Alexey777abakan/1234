import logging
import asyncio
import os
import json
import aiosqlite
import aiohttp
from dotenv import load_dotenv
from aiohttp import web
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 10000))
DATABASE_URL = "users.db"

if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в .env")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL не найден в .env")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# База данных
class Database:
    async def init_db(self):
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def add_user(self, user_id: int):
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

db = Database()

# Состояния FSM
class Form(StatesGroup):
    main_menu = State()

# 📌 Обычная reply-клавиатура (под полем ввода)
def reply_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📢 Реферальные ссылки")],
        [KeyboardButton(text="🤖 Спросить нейросеть")]
    ], resize_keyboard=True)

# 📌 Инлайн-кнопки (прикреплены к сообщению)
def inline_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Реферальные ссылки", callback_data="referral_links")],
        [InlineKeyboardButton(text="🤖 Спросить нейросеть", callback_data="ask_neuro")]
    ])

# 🚀 Обработчик команды /start
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await db.add_user(message.from_user.id)
    await message.answer(
        "👋 Привет! Выберите действие:",
        reply_markup=reply_menu_keyboard()  # Добавляем reply-клавиатуру
    )

# 🚀 Обработчик команды /menu (дублирует /start)
@router.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer(
        "🏠 Главное меню",
        reply_markup=reply_menu_keyboard()
    )

# 🚀 Обработчик команды /help
@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("📚 Доступные команды:\n/start - Главное меню\n/menu - Главное меню\n/help - Помощь")

# 🚀 Обработчик кнопки "📢 Реферальные ссылки"
@router.message(F.text == "📢 Реферальные ссылки")
async def referral_handler_text(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Перейти на сайт", url="https://example.com/referral")]
    ])
    await message.answer("🌐 Ваша реферальная ссылка:", reply_markup=keyboard)

# 🚀 Обработчик инлайн-кнопки "📢 Реферальные ссылки"
@router.callback_query(F.data == "referral_links")
async def referral_handler(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Перейти на сайт", url="https://example.com/referral")]
    ])
    await callback.message.answer("🌐 Ваша реферальная ссылка:", reply_markup=keyboard)
    await callback.answer()

# 🚀 Обработчик кнопки "🤖 Спросить нейросеть"
@router.message(F.text == "🤖 Спросить нейросеть")
async def ask_neuro_text(message: types.Message, state: FSMContext):
    await message.answer("🤖 Введите ваш вопрос:")
    await state.set_state(Form.main_menu)

# 🚀 Обработчик инлайн-кнопки "🤖 Спросить нейросеть"
@router.callback_query(F.data == "ask_neuro")
async def ask_neuro_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🤖 Введите ваш вопрос:")
    await state.set_state(Form.main_menu)

# 🚀 Получение ответа от нейросети
@router.message(Form.main_menu)
async def process_neuro_question(message: types.Message, state: FSMContext):
    await state.clear()
    answer = await get_neuro_answer(message.text)
    await message.answer(f"🤖 Ответ:\n{answer}")

# 🚀 Запрос к нейросети (Claude API)
async def get_neuro_answer(question: str):
    headers = {"Authorization": f"Bearer {os.getenv('CLAUDE_API_KEY')}", "Content-Type": "application/json"}
    data = {"model": os.getenv("CLAUDE_MODEL", "anthropic/claude-3.5-sonnet"), "messages": [{"role": "user", "content": question}]}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(os.getenv("CLAUDE_API_URL"), json=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "Ошибка")
            return "❌ Ошибка связи с нейросетью."

# 📌 Обработчик `/health` (исправляет 404)
async def health_check(request):
    return web.Response(text="OK", status=200)

# 📌 Обработчик вебхука
async def webhook_handler(request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return web.Response(text="OK")

# 📌 Настройка `aiohttp`-сервера
app = web.Application()
app.router.add_get("/health", health_check)  # Проверка работоспособности
app.router.add_post(WEBHOOK_PATH, webhook_handler)  # Вебхук

async def on_startup():
    """Настроить вебхук при старте"""
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)
    logger.info("✅ Webhook установлен!")

async def main():
    """Инициализация бота и запуск веб-сервера"""
    await db.init_db()
    await on_startup()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🚀 Бот запущен на порту {PORT}")

# 📌 Запуск без `asyncio.run()`
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
