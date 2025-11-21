"""
Система блокировки запросов к ИИ.
Если запрос обрабатывается, все новые сообщения игнорируются.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class RequestLock:
    """Менеджер блокировки запросов для каждого пользователя."""
    
    def __init__(self):
        # Активные запросы: user_id -> timestamp начала обработки
        self._active_requests: Dict[int, datetime] = {}
    
    def has_active_request(self, user_id: int) -> bool:
        """Проверяет, есть ли активный запрос для пользователя."""
        return user_id in self._active_requests
    
    def start_request(self, user_id: int) -> None:
        """Отмечает начало обработки запроса."""
        self._active_requests[user_id] = datetime.now()
        logger.debug(f"Начата обработка запроса для user_id={user_id}")
    
    def finish_request(self, user_id: int) -> None:
        """Завершает обработку запроса."""
        if user_id in self._active_requests:
            del self._active_requests[user_id]
            logger.debug(f"Завершена обработка запроса для user_id={user_id}")
    
    def clear(self, user_id: int) -> None:
        """Очищает блокировку для пользователя (например, при остановке чата)."""
        if user_id in self._active_requests:
            del self._active_requests[user_id]
            logger.info(f"Блокировка очищена для user_id={user_id}")


# Глобальный экземпляр блокировки
_request_lock = RequestLock()


def get_request_lock() -> RequestLock:
    """Возвращает глобальный экземпляр блокировки."""
    return _request_lock

