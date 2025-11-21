"""
Модуль с генераторами клавиатур (кнопок) для Telegram-бота.
Все функции — только создание клавиатур.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from refferals.constants import REFERRAL_BUTTON_TEXT

def get_gender_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора пола пользователя.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками "Парень" и "Девушка"
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨 Парень", callback_data="gender:guy"),
                InlineKeyboardButton(text="👩 Девушка", callback_data="gender:girl"),
            ]
        ]
    )
    return keyboard

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главная клавиатура после выбора пола пользователя.
    Содержит кнопки: Профиль, Мои персонажи, Популярные Персонажи.
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Популярные Персонажи", callback_data="menu:popular"),
                InlineKeyboardButton(text="💎 Мои персонажи", callback_data="menu:mychars"),
            ],
            [
                InlineKeyboardButton(text="✨ Профиль", callback_data="menu:profile"),
            ],
            [
                InlineKeyboardButton(text=REFERRAL_BUTTON_TEXT, callback_data="menu:referrals"),
            ],
        ]
    )
    return keyboard

def get_reply_main_menu() -> ReplyKeyboardMarkup:
    """
    Главное меню — видимое снизу.
    Популярные Персонажи на весь тачпад (верхний ряд).
    Мои персонажи по середине, чуть ниже.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⭐ Популярные Персонажи"),
                KeyboardButton(text="💎 Мои персонажи"),
            ],
            [
                KeyboardButton(text="✨ Профиль"),
            ],
            [KeyboardButton(text="💰 Пополнить баланс")],
            [KeyboardButton(text=REFERRAL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def get_reply_characters_menu() -> ReplyKeyboardMarkup:
    """
    Меню, когда пользователь находится в разделе популярных персонажей.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⭐ Популярные Персонажи"),
                KeyboardButton(text="💎 Мои персонажи"),
            ],
            [
                KeyboardButton(text="✨ Профиль"),
            ],
            [KeyboardButton(text="💰 Пополнить баланс")],
            [KeyboardButton(text="🏡 Menu")],
            [KeyboardButton(text=REFERRAL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def get_reply_section_menu() -> ReplyKeyboardMarkup:
    """
    Клавиатура для разделов профиля/персонажей/популярного — с кнопкой "Назад".
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⭐ Популярные Персонажи"),
                KeyboardButton(text="💎 Мои персонажи"),
            ],
            [
                KeyboardButton(text="✨ Профиль"),
            ],
            [KeyboardButton(text="💰 Пополнить баланс")],
            [KeyboardButton(text="🏡 Menu")],
            [KeyboardButton(text=REFERRAL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def get_person_card_keyboard(
    no_prev: bool = False,
    module_file: str | None = None,
    can_delete: bool = False,
    can_chat: bool = False,
    person_index: int | None = None,
) -> InlineKeyboardMarkup:
    """
    Клавиатура для общей анкеты: навигация и, при необходимости, кнопка удаления.
    Использует индекс персонажа вместо полного пути для избежания превышения лимита callback_data.
    """
    rows: list[list[InlineKeyboardButton]] = []
    nav_row: list[InlineKeyboardButton] = []
    if not no_prev:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="character:prev"))
    nav_row.append(InlineKeyboardButton(text="Далее ⏩", callback_data="character:next"))
    rows.append(nav_row)
    if can_chat and person_index is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💭 Начать чат", callback_data=f"character:startchat:{person_index}"
                )
            ]
        )
    if can_delete and person_index is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить", callback_data=f"character:delete:{person_index}"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_reply_my_characters_menu(is_premium: bool = False) -> ReplyKeyboardMarkup:
    """
    Меню при просмотре своих персонажей.
    Вместо кнопки 'Мои персонажи' показываем 'Создать персонажа' (только для премиум).
    """
    keyboard_rows = [
        [
            KeyboardButton(text="⭐ Популярные Персонажи"),
            KeyboardButton(text="💎 Мои персонажи"),
        ],
    ]
    
    # Кнопка "Создать персонажа" только для премиум пользователей
    if is_premium:
        keyboard_rows.append([KeyboardButton(text="✨ Создать персонажа")])
    
    keyboard_rows.extend([
        [
            KeyboardButton(text="✨ Профиль"),
        ],
        [KeyboardButton(text="💰 Пополнить баланс")],
        [KeyboardButton(text="🏡 Menu")],
        [KeyboardButton(text=REFERRAL_BUTTON_TEXT)],
    ])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def get_my_person_card_keyboard(
    no_prev: bool = False,
    noop: bool = False,
    can_publish: bool = False,
    persona_id: int | None = None,
    published: bool = False,
) -> InlineKeyboardMarkup:
    """
    Клавиатура для 'Моих персонажей', чтобы не смешивать callback data.
    """
    rows: list[list[InlineKeyboardButton]] = []
    nav_row: list[InlineKeyboardButton] = []
    if not noop and not no_prev:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="mychar:prev"))
    if not noop:
        nav_row.append(InlineKeyboardButton(text="Далее ⏩", callback_data="mychar:next"))
    if nav_row:
        rows.append(nav_row)
    if can_publish and persona_id is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📣 Опубликовать",
                    callback_data=f"mychar:publish:{persona_id}",
                )
            ]
        )
    elif published:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ Уже опубликован", callback_data="mychar:published"
                )
            ]
        )
    # Кнопка редактирования описания
    if persona_id is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать описание",
                    callback_data=f"mychar:edit_description:{persona_id}",
                )
            ]
        )
    # Кнопка удаления персонажа
    if persona_id is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить персонажа",
                    callback_data=f"mychar:delete:{persona_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
