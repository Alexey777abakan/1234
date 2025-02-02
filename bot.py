import logging
import asyncio
import os
import json
import aiosqlite
import aiohttp
from dotenv import load_dotenv
from aiohttp import web
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 10000))  # Render требует порт 10000
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

# Клавиатура
def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реферальные ссылки", callback_data="referral_links")],
        [InlineKeyboardButton(text="Спросить нейросеть", callback_data="ask_neuro")]
    ])

# Обработчики команд
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await db.add_user(message.from_user.id)
    await message.answer("👋 Привет! Выберите действие:", reply_markup=main_menu_keyboard())

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("📚 Доступные команды:\n/start - Главное меню\n/help - Помощь")

# Обработчики callback-запросов
@router.callback_query(F.data == "referral_links")
async def referral_handler(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти", url="https://example.com/referral")]
    ])
    await callback.message.answer("🌐 Ваша реферальная ссылка:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "ask_neuro")
async def ask_neuro_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🤖 Введите вопрос:")
    await state.set_state(Form.main_menu)

@router.message(Form.main_menu)
async def process_neuro_question(message: types.Message, state: FSMContext):
    await state.clear()
    answer = await get_neuro_answer(message.text)
    await message.answer(f"🤖 Ответ:\n{answer}")

# Запрос к нейросети (пример с Claude API)
async def get_neuro_answer(question: str):
    headers = {"Authorization": f"Bearer {os.getenv('CLAUDE_API_KEY')}", "Content-Type": "application/json"}
    data = {"model": os.getenv("CLAUDE_MODEL", "anthropic/claude-3.5-sonnet"), "messages": [{"role": "user", "content": question}]}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(os.getenv("CLAUDE_API_URL"), json=data, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "Ошибка")
            return "❌ Ошибка связи с нейросетью."

# Настройка вебхука
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)

async def webhook_handler(request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return web.Response()

# Создание aiohttp сервера
app = web.Application()
app.router.add_post(WEBHOOK_PATH, webhook_handler)

# Запуск бота
async def main():
    await db.init_db()
    await bot.delete_webhook()
    if os.getenv("DISABLE_WEBHOOK") == "True":
        await dp.start_polling(bot)
    else:
        await on_startup(bot)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
    asyncio.run(main())
