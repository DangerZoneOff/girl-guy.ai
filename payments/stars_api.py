"""
API клиент для оплаты в Telegram Stars.

Примечание: Telegram Stars работает напрямую через Bot API,
поэтому этот модуль используется только для совместимости
и резервной синхронизации через внешний API (если требуется).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Флаг для использования внешнего API (опционально)
USE_EXTERNAL_API = os.getenv("STARS_USE_EXTERNAL_API", "false").lower() == "true"


def get_stars_api_key() -> Optional[str]:
    """Возвращает API ключ для оплаты в звёздах (если используется внешний API)."""
    return os.getenv("STARS_API_KEY")


class StarsAPIError(Exception):
    """Ошибка при работе с API оплаты в звёздах."""

    pass


async def list_paid_payments(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Возвращает список оплаченных платежей.
    
    Примечание: Если используется внешний API, эта функция будет работать с ним.
    В противном случае возвращает пустой список, так как платежи обрабатываются
    напрямую через обработчики Bot API.
    
    Args:
        limit: Максимальное количество записей
        offset: Смещение для пагинации
    
    Returns:
        Список словарей с данными оплаченных платежей
    """
    if not USE_EXTERNAL_API:
        # Платежи обрабатываются напрямую через обработчики
        return []
    
    # Если требуется интеграция с внешним API, добавьте код здесь
    # Например, через httpx или другой HTTP клиент
    logger.warning("Внешний API для Stars не настроен, но USE_EXTERNAL_API=true")
    return []

