import logging
import asyncio
import aiosqlite
import signal
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from dotenv import load_dotenv
import os
import json
from pathlib import Path
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp  # используется для HTTP-запросов к нейросети

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE", "logs/bot.log"), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
PORT = int(os.getenv("PORT", 10000))  # Render требует порт 10000
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///users.db")
# Работает только режим webhook (polling не используется)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-3.5-sonnet")
CLAUDE_API_URL = os.getenv("CLAUDE_API_URL", "https://proxy.tune.app/chat/completions")

if not API_TOKEN:
    raise ValueError("API_TOKEN не найден в .env")
if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY не найден в .env")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Состояния FSM
class Form(StatesGroup):
    main_menu = State()
    ask_neuro = State()

# Текстовые сообщения
class Texts:
    WELCOME = (
        "👋 Привет! Добро пожаловать в наш бот! 🎉\n\n"
        "Здесь вы можете:\n"
        "💳 Оформить кредит\n"
        "💰 Получить займ\n"
        "🛡️ Оформить страховку\n"
        "💼 Найти работу\n"
        "🎁 Сокровищница выгод\n"
        "🤖 Спросить нейросеть (требуется подписка на канал)\n\n"
        "Выберите действие ниже:"
    )
    HELP = (
        "📚 Помощь:\n"
        "/start - Перезапустить бота\n"
        "/menu - Главное меню"
    )
    MENU = (
        "🏠 Главное меню:\n"
        "💳 Кредитные карты\n"
        "💰 Займы и кредиты\n"
        "🛡️ Страхование\n"
        "💼 Карьерный путь\n"
        "🎁 Сокровищница выгод\n"
        "🤖 Спросить нейросеть (требуется подписка на канал)"
    )

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

    async def increment_question_count(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET questions_count = questions_count + 1 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()

    async def get_question_count(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT questions_count FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_stats(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = await cursor.fetchone()
            cursor = await db.execute("SELECT COUNT(*) FROM users WHERE subscribed = TRUE")
            active_users = await cursor.fetchone()
            return total_users[0], active_users[0]

db = Database()

# Управление клавиатурами через JSON
class KeyboardManager:
    def __init__(self, config_path: str = "keyboards_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Ошибка загрузки конфигурации клавиатур: {str(e)}")

    def get_markup(self, menu_name: str, **kwargs) -> InlineKeyboardMarkup:
        menu_config = self.config.get(menu_name)
        if not menu_config:
            raise ValueError(f"Меню {menu_name} не найдено в конфигурации")
        
        buttons = []
        for row in menu_config["buttons"]:
            keyboard_row = []
            for btn in row:
                text = btn["text"].format(**kwargs)
                if "url" in btn:
                    url = btn["url"].format(**kwargs)
                    keyboard_row.append(InlineKeyboardButton(text=text, url=url))
                elif "callback_data" in btn:
                    callback_data = btn["callback_data"]
                    keyboard_row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
            buttons.append(keyboard_row)
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def get_menu_text(self, menu_name: str) -> str:
        return self.config.get(menu_name, {}).get("text", "")

    def reload_config(self):
        self.config = self._load_config()

keyboard_manager = KeyboardManager()

# Обработчики команд
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await db.add_user(message.from_user.id)
    await message.answer(
        Texts.WELCOME,
        reply_markup=keyboard_manager.get_markup("main_menu")
    )

@router.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    await message.answer(
        Texts.MENU,
        reply_markup=keyboard_manager.get_markup("main_menu")
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
    help_text = Texts.HELP + ("\nАдмин-команды:\n/stats - Статистика\n/reload - Обновить конфиг" if is_admin else "")
    await message.answer(help_text)

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав.")
        return
    total, active = await db.get_stats()
    await message.answer(f"📊 Пользователей: {total}\nАктивных: {active}")

@router.message(Command("reload"))
async def cmd_reload(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав.")
        return
    try:
        keyboard_manager.reload_config()
        await message.answer("✅ Конфиг обновлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# Обработчики колбэков
@router.callback_query(F.data.in_({"credit_cards", "loans", "education", "insurance", "jobs", "online_shops", "promotions", "ask_neuro"}))
async def handle_category(callback: types.CallbackQuery):
    menu_name = f"{callback.data}_menu"
    await callback.message.edit_text(
        keyboard_manager.get_menu_text(menu_name),
        reply_markup=keyboard_manager.get_markup(menu_name)
    )

@router.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        keyboard_manager.get_menu_text("main_menu"),
        reply_markup=keyboard_manager.get_markup("main_menu")
    )

@router.callback_query(F.data == "ask_neuro")
async def ask_neuro_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    # Для обычных пользователей можно добавить проверку подписки, если нужно:
    if user_id not in ADMIN_IDS:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status not in ["member", "administrator", "creator"]:
            await callback.answer("📢 Подпишитесь на канал!", show_alert=True)
            return
    await callback.message.answer("Введите вопрос:")
    await state.set_state(Form.ask_neuro)

@router.message(Form.ask_neuro)
async def process_neuro_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
    # Для обычных пользователей проверяем лимит (5 запросов)
    if not is_admin:
        count = await db.get_question_count(user_id)
        if count >= 5:
            await message.answer("❌ Лимит вопросов исчерпан.")
            await state.clear()  # Выходим из режима вопросов
            return
        else:
            await db.increment_question_count(user_id)
    # Получаем ответ от нейросети с учетом роли
    answer = await get_neuro_answer(message.text, is_admin=is_admin)
    await message.answer(f"🤖 Ответ:\n{answer}")
    # Состояние не сбрасывается, чтобы пользователь мог продолжать задавать вопросы до исчерпания лимита

# Функция для запроса к нейросети (Claude API)
async def get_neuro_answer(question: str, is_admin: bool = False):
    headers = {
        "Authorization": f"Bearer {CLAUDE_API_KEY}",
        "Content-Type": "application/json"
    }
    # Для обычных пользователей лимит = 200, для администраторов = 4000
    max_tokens = 4000 if is_admin else 200
    data = {
        "model": CLAUDE_MODEL,
        "messages": [{"role": "user", "content": question}],
        "max_tokens": max_tokens
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                CLAUDE_API_URL,
                headers=headers,
                json=data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Claude API Error: {response.status} - {error}")
                    return "⚠️ Ошибка нейросети."
                result = await response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа.")
    except asyncio.TimeoutError:
        logger.error("Claude API Timeout")
        return "⌛ Таймаут."
    except Exception as e:
        logger.error(f"Claude Error: {str(e)}")
        return "⚠️ Ошибка."

# Веб-сервер
async def health_check(request):
    return web.Response(text="OK")

async def webhook_handler(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

# Основная функция запуска в режиме webhook
async def main():
    # Удаляем предыдущий webhook (если был установлен)
    await bot.delete_webhook(drop_pending_updates=True)
    # Инициализация базы данных
    await db.init_db()
    # Создаем веб-приложение aiohttp
    app = web.Application()
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_get("/health", health_check)
    # Создаем и запускаем AppRunner и сайт
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    # Устанавливаем webhook (замените URL на ваш публичный домен)
    webhook_url = "https://my-telegram-bot-yb0n.onrender.com/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"Сервер запущен на порту {PORT}, webhook установлен: {webhook_url}")
    # Ожидание сигнала завершения работы
    stop_event = asyncio.Event()
    # Функция для graceful shutdown
    async def shutdown():
        logger.info("Завершение работы...")
        await bot.session.close()
        await runner.cleanup()
        stop_event.set()
    # Регистрируем обработчики сигналов SIGINT и SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    await stop_event.wait()

if __name__ == "__main__":
    asyncio.run(main())