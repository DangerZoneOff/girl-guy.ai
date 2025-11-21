"""
Базовые настройки и проверки прав администратора.
"""

from __future__ import annotations

ADMIN_IDS: set[int] = {1435679803}


def is_admin(user_id: int | None) -> bool:
    """
    Возвращает True, если указанный пользователь — администратор.
    """
    if user_id is None:
        return False
    return int(user_id) in ADMIN_IDS

