"""
Управление премиум подписками.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from SMS.database import get_db_connection, init_database

logger = logging.getLogger(__name__)

# Премиум тарифы
PREMIUM_PLANS = {
    1: {
        "weeks": 1,
        "price_stars": 1,
        "tokens": 100,  # Токены начисляются на баланс
        "unlimited": False,
    },
    2: {
        "weeks": 2,
        "price_stars": 450,  # Скидка 10% от 500
        "tokens": 350,
        "unlimited": False,
    },
    3: {
        "weeks": 3,
        "price_stars": 660,  # Скидка ~12% от 750
        "tokens": 750,
        "unlimited": False,
    },
    4: {
        "weeks": 4,  # Для совместимости, но отображается как "1 месяц"
        "months": 1,
        "price_stars": 999,
        "tokens": 0,  # Безлимит - токены не начисляются, но и не списываются
        "unlimited": True,
    },
}


def init_premium_database() -> None:
    """Инициализирует таблицу премиум подписок."""
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Таблица премиум подписок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS premium_subscriptions (
                user_id INTEGER PRIMARY KEY,
                is_active BOOLEAN DEFAULT 0,
                plan_type INTEGER DEFAULT 1,
                activated_at TIMESTAMP,
                expires_at TIMESTAMP,
                last_weekly_tokens TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Добавляем поле plan_type если его нет
        try:
            cursor.execute("ALTER TABLE premium_subscriptions ADD COLUMN plan_type INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        
        # Индекс для быстрого поиска активных подписок
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_premium_active 
            ON premium_subscriptions(is_active, expires_at)
        """)
        
        # commit выполняется автоматически контекстным менеджером
        logger.info("Таблица premium_subscriptions инициализирована")


def is_premium(user_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя активная премиум подписка.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True если подписка активна и не истекла
    """
    init_premium_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_active, expires_at 
            FROM premium_subscriptions 
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return False
        
        is_active = bool(row["is_active"])
        expires_at_str = row["expires_at"]
        
        if not is_active or not expires_at_str:
            return False
        
        # Проверяем, не истекла ли подписка
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.now().tzinfo)
            
            now = datetime.now(expires_at.tzinfo)
            if now >= expires_at:
                # Подписка истекла, деактивируем
                cursor.execute("""
                    UPDATE premium_subscriptions 
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                # commit выполняется автоматически контекстным менеджером
                return False
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при проверке срока подписки для user_id={user_id}: {e}")
            return False


def get_premium_status(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает статус премиум подписки пользователя.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Словарь с информацией о подписке или None
    """
    init_premium_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM premium_subscriptions WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # sqlite3.Row не имеет метода .get(), используем прямой доступ с обработкой KeyError
        try:
            plan_type = row["plan_type"]
        except (KeyError, IndexError):
            plan_type = 1  # Значение по умолчанию
        
        return {
            "is_active": bool(row["is_active"]),
            "plan_type": plan_type,
            "activated_at": row["activated_at"],
            "expires_at": row["expires_at"],
            "last_weekly_tokens": row["last_weekly_tokens"],
        }


def activate_premium(user_id: int, plan_type: int) -> bool:
    """
    Активирует премиум подписку для пользователя.
    
    Args:
        user_id: ID пользователя
        plan_type: Тип тарифа (1, 2, 3 недели или 4 - 1 месяц)
        
    Returns:
        True если успешно активировано
    """
    if plan_type not in PREMIUM_PLANS:
        logger.error(f"Неверный тип тарифа: {plan_type}")
        return False
    
    plan = PREMIUM_PLANS[plan_type]
    init_premium_database()
    
    now = datetime.now()
    # Для плана 4 (месяц) используем 30 дней, для остальных - недели * 7
    if plan_type == 4:
        duration_days = 30  # 1 месяц = 30 дней
    else:
        duration_days = plan["weeks"] * 7
    expires_at = now + timedelta(days=duration_days)
    
    tokens_to_add = 0
    if not plan.get("unlimited", False):
        tokens_to_add = max(0, plan.get("tokens", 0))
    
    success = False
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже подписка
        cursor.execute("SELECT * FROM premium_subscriptions WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующую подписку
            current_expires = existing["expires_at"]
            if current_expires:
                try:
                    current_expires_dt = datetime.fromisoformat(current_expires.replace("Z", "+00:00"))
                    if current_expires_dt.tzinfo is None:
                        current_expires_dt = current_expires_dt.replace(tzinfo=now.tzinfo)
                    
                    # Если подписка еще активна, продлеваем от текущей даты окончания
                    if now < current_expires_dt:
                        expires_at = current_expires_dt + timedelta(days=duration_days)
                except Exception:
                    pass  # Используем новую дату
            
            cursor.execute("""
                UPDATE premium_subscriptions 
                SET is_active = 1,
                    plan_type = ?,
                    activated_at = ?,
                    expires_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (plan_type, now.isoformat(), expires_at.isoformat(), user_id))
        else:
            # Создаем новую подписку
            cursor.execute("""
                INSERT INTO premium_subscriptions 
                (user_id, is_active, plan_type, activated_at, expires_at)
                VALUES (?, 1, ?, ?, ?)
            """, (user_id, plan_type, now.isoformat(), expires_at.isoformat()))
        
        # commit выполняется автоматически контекстным менеджером
        logger.info(f"Премиум подписка активирована для user_id={user_id}, план={plan_type}, до {expires_at.isoformat()}")
        success = True
    
    if success and tokens_to_add > 0:
        try:
            from SMS.tokens import add_tokens
            add_tokens(user_id, tokens_to_add)
            logger.info(f"Начислено {tokens_to_add} токенов на баланс для user_id={user_id}")
        except Exception as e:
            logger.error(f"Не удалось начислить токены премиум пользователю {user_id}: {e}")
    
    return success


def deactivate_premium(user_id: int) -> bool:
    """
    Деактивирует премиум подписку пользователя.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True если успешно деактивировано
    """
    init_premium_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE premium_subscriptions 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))
        affected = cursor.rowcount
        # commit выполняется автоматически контекстным менеджером
        
        if affected > 0:
            logger.info(f"Премиум подписка деактивирована для user_id={user_id}")
        
        return affected > 0


def get_premium_expiry(user_id: int) -> Optional[datetime]:
    """
    Получает дату окончания премиум подписки.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Дата окончания или None
    """
    status = get_premium_status(user_id)
    if not status or not status.get("expires_at"):
        return None
    
    try:
        expires_at_str = status["expires_at"]
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.now().tzinfo)
        return expires_at
    except Exception as e:
        logger.error(f"Ошибка при парсинге даты окончания для user_id={user_id}: {e}")
        return None


def is_premium_unlimited(user_id: int) -> bool:
    """
    Проверяет, есть ли у пользователя безлимитная премиум подписка (тариф 4).
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True если подписка активна и безлимитная
    """
    if not is_premium(user_id):
        return False
    
    status = get_premium_status(user_id)
    if not status:
        return False
    
    plan_type = status.get("plan_type", 1)
    plan = PREMIUM_PLANS.get(plan_type)
    
    if not plan:
        return False
    
    return plan.get("unlimited", False)


def add_weekly_tokens(user_id: int) -> bool:
    """
    Добавляет еженедельные токены премиум пользователю.
    Проверяет, прошла ли неделя с последнего начисления.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True если токены были добавлены
    """
    if not is_premium(user_id):
        return False
    
    init_premium_database()
    
    now = datetime.now()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT last_weekly_tokens FROM premium_subscriptions WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if row and row["last_weekly_tokens"]:
            try:
                last_tokens = datetime.fromisoformat(row["last_weekly_tokens"].replace("Z", "+00:00"))
                if last_tokens.tzinfo is None:
                    last_tokens = last_tokens.replace(tzinfo=now.tzinfo)
                
                # Проверяем, прошла ли неделя
                if (now - last_tokens).days < 7:
                    return False  # Еще не прошла неделя
            except Exception:
                pass  # Если ошибка парсинга, начисляем токены
    
    from SMS.tokens import add_tokens
    add_tokens(user_id, PREMIUM_WEEKLY_TOKENS)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE premium_subscriptions 
            SET last_weekly_tokens = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (now.isoformat(), user_id))
        # commit выполняется автоматически контекстным менеджером
    
    logger.info(f"Начислено {PREMIUM_WEEKLY_TOKENS} еженедельных токенов для user_id={user_id}")
    return True

