"""
Бизнес-логика реферальной программы.
"""

from __future__ import annotations

import logging
from typing import Optional

from SMS.database import get_db_connection, init_database
from SMS.tokens import add_tokens

from . import constants

logger = logging.getLogger(__name__)

REF_PREFIX = "ref_"


def _encode_ref_code(user_id: int) -> str:
    return str(user_id)


def _decode_ref_code(code: str) -> Optional[int]:
    code = code.strip().lower()
    if code.startswith(REF_PREFIX):
        code = code[len(REF_PREFIX):]
    elif code.startswith("ref"):
        code = code[3:]
    if not code.isdigit():
        return None
    try:
        return int(code)
    except ValueError:
        return None


def get_referral_link(user_id: int) -> str:
    """
    Возвращает ссылку вида https://t.me/<bot>?start=ref_<code>.
    Если имя бота не задано, вернёт payload ref_<code>.
    """
    code = _encode_ref_code(user_id)
    bot_username = constants.BOT_USERNAME
    if bot_username:
        return f"https://t.me/{bot_username}?start={REF_PREFIX}{code}"
    return f"{REF_PREFIX}{code}"


def get_referral_stats(user_id: int) -> dict:
    """Возвращает статистику пользователя по рефералам."""
    init_database()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN rewarded = 1 THEN 1 ELSE 0 END) AS rewarded
            FROM referral_relations
            WHERE referrer_id = ?
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        total = row["total"] if row and row["total"] is not None else 0
        rewarded = row["rewarded"] if row and row["rewarded"] is not None else 0
    return {
        "invited": total,
        "rewarded": rewarded,
        "earned_tokens": rewarded * constants.REFERRAL_REWARD_TOKENS,
    }


def process_referral_payload(user_id: int, payload: Optional[str]) -> Optional[str]:
    """
    Обрабатывает payload команды /start и начисляет награду рефереру.
    Возвращает сообщение для приглашённого пользователя или None.
    """
    if not payload:
        return None
    referrer_id = _decode_ref_code(payload)
    if not referrer_id:
        return None
    status = _register_referral(referrer_id=referrer_id, invited_user_id=user_id)
    if status == "self":
        return "🙈 Нельзя использовать свою собственную реферальную ссылку."
    if status == "duplicate":
        return None
    if status == "success":
        return (
            f"🎉 Ты пришёл по ссылке друга! "
            f"Ему начислено <b>{constants.REFERRAL_REWARD_TOKENS} токенов</b>."
        )
    return None


def _register_referral(referrer_id: int, invited_user_id: int) -> str:
    """
    Пытается привязать приглашенного пользователя к рефереру.
    Возвращает статус: success, duplicate, self, invalid.
    """
    if referrer_id == invited_user_id:
        return "self"
    
    init_database()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Проверяем, не зарегистрирован ли уже пользователь
            cursor.execute(
                "SELECT referrer_id FROM referral_relations WHERE invited_user_id = ?",
                (invited_user_id,),
            )
            row = cursor.fetchone()
            if row:
                return "duplicate"
            
            # Регистрируем реферала
            cursor.execute(
                """
                INSERT INTO referral_relations (invited_user_id, referrer_id, rewarded)
                VALUES (?, ?, 0)
                """,
                (invited_user_id, referrer_id),
            )
            
            # Начисляем токены рефереру
            add_tokens(referrer_id, constants.REFERRAL_REWARD_TOKENS)
            
            # Отмечаем, что награда выдана
            cursor.execute(
                "UPDATE referral_relations SET rewarded = 1 WHERE invited_user_id = ?",
                (invited_user_id,),
            )
            # commit выполняется автоматически контекстным менеджером
    except Exception as e:
        logger.error("Ошибка при регистрации реферала: user=%s ref=%s err=%s", invited_user_id, referrer_id, e)
        return "invalid"
    
    return "success"


