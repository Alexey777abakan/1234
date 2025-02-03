from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Функция для создания главного меню
def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Кредитные карты", callback_data="credit_cards"),
            InlineKeyboardButton(text="💰 Займы", callback_data="loans")
        ],
        [
            InlineKeyboardButton(text="🎓 Образование", callback_data="education"),
            InlineKeyboardButton(text="🛡️ Страхование", callback_data="insurance")
        ],
        [
            InlineKeyboardButton(text="💼 Работа", callback_data="jobs"),
            InlineKeyboardButton(text="🏪 Магазины онлайн", callback_data="online_shops")
        ],
        [
            InlineKeyboardButton(text="🎁 Акции", callback_data="promotions"),
            InlineKeyboardButton(text="🤖 Спросить нейросеть", callback_data="ask_neuro")
        ],
        [
            InlineKeyboardButton(text="💝 Поддержать проект", url="https://clck.ru/3GA7zP")
        ]
    ])
    return keyboard

# Функция для создания меню "Кредитные карты"
def get_credit_cards_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Кредитный навигатор", url="https://clck.ru/3GA7nq"),
            InlineKeyboardButton(text="СберБанк - Кредитная СберКарта", url="https://clck.ru/3GA7nv")
        ],
        [
            InlineKeyboardButton(text="Т-Банк - Кредитная карта Платинум", url="https://clck.ru/3GA7o2"),
            InlineKeyboardButton(text="Уралсиб - Кредитная карта с кешбэком", url="https://clck.ru/3GA7oC")
        ],
        [
            InlineKeyboardButton(text="Уралсиб - Кредитная карта 120 дней без %", url="https://clck.ru/3GA7oF"),
            InlineKeyboardButton(text="Т-Банк — Кредитная карта Платинум// Кешбэк 2 000 рублей", url="https://clck.ru/3GA7oL")
        ],
        [
            InlineKeyboardButton(text="Совкомбанк - Карта рассрочки Халва МИР", url="https://clck.ru/3GA7oS"),
            InlineKeyboardButton(text="Одобрение - Помощь в получение кредита после банкротства", url="https://clck.ru/3GA7oa")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Займы"
def get_loans_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Витрина займов: деньги под рукой!", url="https://clck.ru/3GA7on"),
            InlineKeyboardButton(text="Займер", url="https://clck.ru/3GA7oq")
        ],
        [
            InlineKeyboardButton(text="Cashiro", url="https://clck.ru/3GA7ow"),
            InlineKeyboardButton(text="До Зарплаты", url="https://clck.ru/3GA7p2")
        ],
        [
            InlineKeyboardButton(text="Небус", url="https://clck.ru/3GA7p7"),
            InlineKeyboardButton(text="Max.Credit", url="https://clck.ru/3GA7pJ")
        ],
        [
            InlineKeyboardButton(text="еКапуста", url="https://clck.ru/3GA7pM"),
            InlineKeyboardButton(text="MoneyMan", url="https://clck.ru/3GA7pX")
        ],
        [
            InlineKeyboardButton(text="Joymoney", url="https://clck.ru/3GA7pc"),
            InlineKeyboardButton(text="Деньги на дом", url="https://clck.ru/3GA7pc")
        ],
        [
            InlineKeyboardButton(text="ДоброЗайм", url="https://clck.ru/3GA7po"),
            InlineKeyboardButton(text="Целевые финансы", url="https://clck.ru/3GA7pv")
        ],
        [
            InlineKeyboardButton(text="Быстроденьги", url="https://clck.ru/3GA7pw"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Образование"
def get_education_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Яндекс.Практикум", url="https://clck.ru/3GA7vc"),
            InlineKeyboardButton(text="Eduson.academy", url="https://clck.ru/3GA7vf")
        ],
        [
            InlineKeyboardButton(text="99ballov.ru", url="https://clck.ru/3GA7vm"),
            InlineKeyboardButton(text="Школа Московской Биржи - Курс 'Деньги делают деньги'", url="https://clck.ru/3GA7vp")
        ],
        [
            InlineKeyboardButton(text="100points.ru", url="https://clck.ru/3GA7vv"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Страхование"
def get_insurance_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Осаго", url="https://clck.ru/3GA7tK"),
            InlineKeyboardButton(text="Страхование ипотеки", url="https://clck.ru/3GA7tQ")
        ],
        [
            InlineKeyboardButton(text="Zetta - ОСГОП", url="https://clck.ru/3GA7tV"),
            InlineKeyboardButton(text="АльфаСтрахование - ОСГОП", url="https://clck.ru/3GA7tf")
        ],
        [
            InlineKeyboardButton(text="Zetta - Страхование имущества", url="https://clck.ru/3GA7to"),
            InlineKeyboardButton(text="Согласие - Имущество", url="https://clck.ru/3GA7tz")
        ],
        [
            InlineKeyboardButton(text="Ренессанс Жизнь - Смарт Плюс", url="https://clck.ru/3GA7uA"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Работа"
def get_jobs_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Витрина", url="https://clck.ru/3GA7rb"),
            InlineKeyboardButton(text="Курьер в Яндекс.Еда/Яндекс.Лавка", url="https://clck.ru/3GA7ri")
        ],
        [
            InlineKeyboardButton(text="Магнит // Водитель категории Е", url="https://clck.ru/3GA7ro"),
            InlineKeyboardButton(text="Курьер/Повар-кассир в Burger King", url="https://clck.ru/3GA7rt")
        ],
        [
            InlineKeyboardButton(text="Альфа банк // Специалист по доставке пластиковых карт", url="https://clck.ru/3GA7s3"),
            InlineKeyboardButton(text="Т-Банк — Работа в Т-Банке", url="https://clck.ru/3GA7s6")
        ],
        [
            InlineKeyboardButton(text="Специалист по продажам услуг МТС", url="https://clck.ru/3GA7sJ"),
            InlineKeyboardButton(text="СберМаркет // Вакансии", url="https://clck.ru/3GA7sP")
        ],
        [
            InlineKeyboardButton(text="Оператор call-центра МТС", url="https://clck.ru/3GA7sb"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Магазины онлайн"
def get_online_shops_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="AliExpress", url="https://clck.ru/3GA7v6"),
            InlineKeyboardButton(text="Yandex market", url="https://clck.ru/3GA7vH")
        ],
        [
            InlineKeyboardButton(text="Shopping Live", url="https://clck.ru/3GA7vP"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Акции"
def get_promotions_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сокровищница выгод: ваш подарок уже ждет!", url="https://clck.ru/3GA7wD")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard

# Функция для создания меню "Спросить нейросеть"
def get_ask_neuro_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])
    return keyboard