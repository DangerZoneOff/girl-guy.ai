"""
Хранилище профилей пользователей.
Использует SQLite для масштабируемости.
"""

from __future__ import annotations

from datetime import datetime
import logging

from SMS.database import get_db_connection, init_database

logger = logging.getLogger(__name__)


def set_registration_date(user_id: int) -> None:
    """Устанавливает дату регистрации пользователя."""
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        reg_date = datetime.now().strftime('%d.%m.%Y %H:%M')
        cursor.execute(
            """
            INSERT INTO user_profiles (user_id, reg_date, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                reg_date = COALESCE(reg_date, ?),
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, reg_date, reg_date)
        )
        logger.info(f"Установлена дата регистрации для user_id={user_id}: {reg_date}")


def get_registration_date(user_id: int) -> str | None:
    """Получает дату регистрации пользователя."""
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT reg_date FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return row["reg_date"]
        return None
