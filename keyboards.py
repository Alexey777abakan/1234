import json
from pathlib import Path
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

# Инициализация KeyboardManager
keyboard_manager = KeyboardManager()