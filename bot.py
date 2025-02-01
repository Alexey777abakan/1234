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
import json
from pathlib import Path
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Загрузка переменных окружения
load_dotenv()

# Настройка логгирования
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
CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")  # Канал для подписки
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
PORT = int(os.getenv("PORT", 5000))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///users.db")
DISABLE_WEBHOOK = os.getenv("DISABLE_WEBHOOK", "True").lower() == "true"
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
    ask_neuro = State()  # Состояние для вопроса к нейросети

# Текстовые сообщения
class Texts:
    WELCOME = (
        "👋 Привет! Добро пожаловать в наш бот! 🎉\n\n"
        "Здесь вы можете:\n"
        "💳 Оформить кредит\n"
        "💰 Получить займ\n"
        "🛡️ Оформить страховку\n"
        "💼 Найти работу\n"
        "🤖 Спросить нейросеть (требуется подписка на канал)\n\n"
        "Выберите действие ниже:"
    )
    HELP = """
    📚 Помощь:
    /start - Перезапустить бота
    /menu - Главное меню
    """
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
        self.db_path = db_path or DATABASE_URL  # Используем DATABASE_URL из .env

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
                    keyboard_row.append(InlineKeyboardButton(
                        text=text, 
                        callback_data=callback_data
                    ))
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
    await show_main_menu(message)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    help_text = Texts.HELP
    if is_admin:
        help_text += "\nАдмин-команды:\n/stats - Статистика\n/reload - Обновить конфиг"

    await message.answer(help_text)

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    total, active = await db.get_stats()
    await message.answer(
        f"📊 Статистика:\n"
        f"Всего пользователей: {total}\n"
        f"Активных подписчиков: {active}"
    )

@router.message(Command("reload"))
async def cmd_reload(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

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
    menu_name = f"{category}_menu"
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
    is_admin = user_id in ADMIN_IDS

    # Проверка подписки на канал (только для обычных пользователей)
    if not is_admin:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status not in ["member", "administrator", "creator"]:
            await callback.answer("📢 Для использования этой функции подпишитесь на канал!", show_alert=True)
            return

    # Проверка лимита вопросов для обычных пользователей
    if not is_admin:
        question_count = await db.get_question_count(user_id)
        if question_count >= 5:
            await callback.answer("❌ Вы исчерпали лимит вопросов (5 вопросов).", show_alert=True)
            return

    await callback.message.answer("Введите ваш вопрос:")
    await state.set_state(Form.ask_neuro)

@router.message(Form.ask_neuro)
async def process_neuro_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS

    # Увеличиваем счетчик вопросов только для обычных пользователей
    if not is_admin:
        await db.increment_question_count(user_id)

    # Получаем ответ от нейросети
    question = message.text
    answer = await get_neuro_answer(question)

    # Отправляем ответ пользователю
    await message.answer(f"🤖 Ответ на ваш вопрос:\n{answer}")
    await state.clear()

# Функция для запроса к Claude API
async def get_neuro_answer(question: str):
    headers = {
        "Authorization": f"Bearer {CLAUDE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": CLAUDE_MODEL,
        "messages": [
            {"role": "user", "content": question}
        ],
        "max_tokens": 200  # Ограничение на длину ответа
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(CLAUDE_API_URL, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return answer.strip() or "Ошибка при получении ответа."
                else:
                    error_message = await response.text()
                    logger.error(f"Ошибка Claude API: {response.status}, {error_message}")
                    return "⚠️ Произошла ошибка при обращении к нейросети."
    except Exception as e:
        logger.error(f"Ошибка при обращении к Claude API: {e}")
        return "⚠️ Произошла ошибка при обращении к нейросети."

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
    
    if DISABLE_WEBHOOK:
        logger.info("Запуск бота в режиме polling...")
        await dp.start_polling(bot)
    else:
        logger.info("Запуск бота в режиме webhook...")
        await bot.set_webhook(url="https://your-domain.com/webhook")
        app = web.Application()
        app.router.add_post("/webhook", dp.process_update)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, port=PORT)
        await site.start()
        logger.info(f"Сервер запущен на порту {PORT}")
    
    # Обработка сигналов завершения
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda: asyncio.create_task(shutdown(sig, loop, bot))
        )

if __name__ == "__main__":
    asyncio.run(main())