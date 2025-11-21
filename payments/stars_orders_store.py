"""
Хранилище обработанных платежей в Telegram Stars.
Использует SQLite для масштабируемости.
"""

from __future__ import annotations

import logging
from typing import Optional

from SMS.database import get_db_connection, init_database

logger = logging.getLogger(__name__)


def was_processed(payment_id: str) -> bool:
    """Проверяет, был ли платеж уже обработан."""
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM stars_orders WHERE payment_id = ? AND status = 'paid'",
            (payment_id,)
        )
        return cursor.fetchone() is not None


def mark_processed(
    payment_id: str, 
    status: str = "paid", 
    tokens: Optional[int] = None,
    user_id: Optional[int] = None
) -> None:
    """Помечает платеж как обработанный."""
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO stars_orders (payment_id, user_id, status, tokens, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(payment_id) DO UPDATE SET
                status = ?,
                tokens = ?,
                user_id = COALESCE(?, user_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (payment_id, user_id, status, tokens, status, tokens, user_id)
        )
        logger.info(f"Платёж {payment_id} помечен как {status}, токены: {tokens}")

