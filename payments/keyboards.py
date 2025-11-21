"""
Inline-клавиатуры для выбора пакетов токенов.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .products import iter_token_packs


def get_token_packs_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с пакетами для оплаты в Telegram Stars."""
    rows: list[list[InlineKeyboardButton]] = []
    for pack in iter_token_packs():
        # Для оплаты в звёздах используем callback, который создаст платёж
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{pack.title} · {pack.price_amount}⭐",
                    callback_data=f"stars:pay:{pack.pack_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="❓ Как это работает",
                callback_data="pay:help",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
