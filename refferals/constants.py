"""
Константы для модуля рефералок.
"""

from __future__ import annotations

import os

REFERRAL_BUTTON_TEXT = "🎁 Рефералы"
REFERRAL_REWARD_TOKENS = int(os.getenv("REFERRAL_REWARD_TOKENS", "15"))
# Загружаем имя бота из переменной окружения (если уже указана)
BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")


def set_bot_username(username: str | None) -> None:
    """Обновляет username бота для формирования реферальных ссылок."""
    global BOT_USERNAME
    if not username:
        return
    BOT_USERNAME = username.strip().lstrip("@")

