"""
Простой помощник для оплаты через Tribute (Telegram Stars).
"""

from __future__ import annotations

import os

DEFAULT_TRIBUTE_URL = "https://t.me/tribute/app?startapp=pna9"


def get_tribute_url() -> str:
    """
    Возвращает ссылку на мини-приложение Tribute.
    Можно переопределить через переменную окружения TRIBUTE_STARTAPP_URL.
    """
    return os.getenv("TRIBUTE_STARTAPP_URL", DEFAULT_TRIBUTE_URL)


