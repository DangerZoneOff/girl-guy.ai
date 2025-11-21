"""
Хранилище токенов пользователей для учета запросов к ИИ.
Использует SQLite для масштабируемости.
"""

from __future__ import annotations

import os
import logging
import sqlite3
import time

from .database import get_db_connection, init_database

logger = logging.getLogger(__name__)

DEFAULT_START_TOKENS = int(os.getenv("SMS_DEFAULT_TOKENS", "20"))


def get_token_balance(user_id: int) -> int:
    """Получает баланс токенов пользователя."""
    import time
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            init_database()
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT tokens FROM token_balances WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    tokens_value = row["tokens"]
                    # Обрабатываем пустые строки, None и другие некорректные значения
                    if tokens_value is None or tokens_value == '':
                        # Возвращаем 0, обновление БД сделаем позже асинхронно (не блокируем)
                        logger.debug(f"Пустое значение токенов для user_id={user_id}, возвращаем 0")
                        return 0
                    try:
                        balance = int(tokens_value)
                        return balance
                    except (ValueError, TypeError):
                        # Если не удалось преобразовать в int, возвращаем 0
                        logger.warning(f"Некорректное значение токенов для user_id={user_id}: {tokens_value}, возвращаем 0")
                        return 0
                
                # Создаём новый аккаунт с начальным балансом (используем ON CONFLICT для защиты от race condition)
                cursor.execute(
                    """
                    INSERT INTO token_balances (user_id, tokens, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO NOTHING
                    """,
                    (user_id, DEFAULT_START_TOKENS)
                )
                # Если запись уже существует (race condition), получаем её значение
                cursor.execute("SELECT tokens FROM token_balances WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        balance = int(row["tokens"])
                        logger.info(f"Аккаунт для user_id={user_id} уже существует, баланс: {balance}")
                        return balance
                    except (ValueError, TypeError):
                        pass
                logger.info(f"Создан новый аккаунт для user_id={user_id} с {DEFAULT_START_TOKENS} токенами")
                return DEFAULT_START_TOKENS
                
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                # БД заблокирована, ждём и повторяем
                time.sleep(retry_delay * (attempt + 1))
                continue
            else:
                # Если все попытки исчерпаны или другая ошибка, логируем и возвращаем 0
                logger.error(f"Ошибка БД при получении баланса для user_id={user_id}: {e}, возвращаем 0")
                return 0
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении баланса для user_id={user_id}: {e}")
            return 0
    
    # Если все попытки исчерпаны
    return 0


def set_token_balance(user_id: int, amount: int) -> int:
    """Устанавливает баланс токенов пользователя."""
    if amount < 0:
        amount = 0
    
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO token_balances (user_id, tokens, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                tokens = ?,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, amount, amount)
        )
        # Явно делаем commit для гарантии сохранения
        conn.commit()
        logger.info(f"Установлен баланс {amount} токенов для user_id={user_id}")
        return amount


def add_tokens(user_id: int, amount: int) -> int:
    """Добавляет токены пользователю."""
    if amount == 0:
        return get_token_balance(user_id)
    
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Получаем текущий баланс
        cursor.execute("SELECT tokens FROM token_balances WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            tokens_value = row["tokens"]
            # Обрабатываем пустые строки, None и другие некорректные значения
            if tokens_value is None or tokens_value == '':
                current = 0
            else:
                try:
                    current = int(tokens_value)
                except (ValueError, TypeError):
                    current = 0
        else:
            # Пользователя нет, начинаем с начального баланса
            current = DEFAULT_START_TOKENS
        
        new_balance = max(0, current + amount)
        
        # Атомарно обновляем или создаем запись
        cursor.execute(
            """
            INSERT INTO token_balances (user_id, tokens, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                tokens = ?,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, new_balance, new_balance)
        )
        # Явно делаем commit для гарантии сохранения
        conn.commit()
        logger.info(f"Добавлено {amount} токенов пользователю {user_id}, баланс: {new_balance}")
        return new_balance


def consume_tokens(user_id: int, amount: int = 1) -> bool:
    """
    Списывает токены у пользователя.
    Для премиум пользователей токены не списываются (безлимит).
    """
    if amount <= 0:
        return True
    
    # Проверяем безлимитный премиум статус (только тариф 4)
    try:
        from premium.subscription import is_premium_unlimited
        if is_premium_unlimited(user_id):
            # Безлимитный премиум - не списываем токены
            return True
    except Exception as e:
        logger.warning(f"Ошибка при проверке премиум статуса для user_id={user_id}: {e}")
        # Продолжаем обычную логику при ошибке
    
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Получаем текущий баланс
        cursor.execute("SELECT tokens FROM token_balances WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            # Аккаунт не существует, создаём с начальным балансом
            current = DEFAULT_START_TOKENS
        else:
            tokens_value = row["tokens"]
            # Обрабатываем пустые строки, None и другие некорректные значения
            if tokens_value is None or tokens_value == '':
                current = 0
            else:
                try:
                    current = int(tokens_value)
                except (ValueError, TypeError):
                    current = 0
        
        if current < amount:
            return False
        
        # Списываем токены
        new_balance = current - amount
        
        # Атомарно обновляем или создаем запись
        cursor.execute(
            """
            INSERT INTO token_balances (user_id, tokens, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                tokens = ?,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, new_balance, new_balance)
        )
        # Явно делаем commit для гарантии сохранения
        conn.commit()
        logger.info(f"Списано {amount} токенов у user_id={user_id}, новый баланс: {new_balance}")
        return True


__all__ = [
    "get_token_balance",
    "set_token_balance",
    "add_tokens",
    "consume_tokens",
]


