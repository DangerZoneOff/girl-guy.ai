"""
Функция удаления персонажей для обычных пользователей.
Позволяет удалять только своих персонажей (не чужих).
"""

from __future__ import annotations

import logging
from pers.database import delete_persona as db_delete_persona, get_persona_by_id
from pers.storage import delete_photo
from knops.api_persons import invalidate_cache

logger = logging.getLogger(__name__)


async def delete_user_persona(persona_id: int, user_id: int) -> tuple[bool, str]:
    """
    Удаляет персонажа пользователя, если он принадлежит этому пользователю.
    
    Args:
        persona_id: ID персонажа для удаления
        user_id: ID пользователя, который пытается удалить
    
    Returns:
        Tuple[bool, str]: (успешно ли удалено, сообщение об ошибке или успехе)
    """
    # Получаем данные персонажа перед удалением
    persona = get_persona_by_id(persona_id)
    if not persona:
        return False, "Персонаж не найден."
    
    # Проверяем, что персонаж принадлежит пользователю
    persona_owner_id = persona.get("owner_id")
    if persona_owner_id != user_id:
        logger.warning(f"Попытка удаления чужого персонажа: user_id={user_id}, persona_owner={persona_owner_id}, persona_id={persona_id}")
        return False, "Вы можете удалять только своих персонажей."
    
    # Удаляем фото (из облака или локально)
    photo_path = persona.get("photo_path")
    photo_url = persona.get("photo_url")
    name = persona.get("name")
    if photo_path or photo_url:
        try:
            await delete_photo(photo_path, photo_url, user_id, name)
            logger.info(f"Фото удалено: {photo_path or photo_url}")
        except Exception as e:
            logger.error(f"Ошибка удаления фото: {e}")
            # Продолжаем удаление даже если фото не удалилось
    
    # Удаляем из БД
    removed = db_delete_persona(persona_id)
    
    if removed:
        # Очищаем кэш профилей после удаления
        invalidate_cache()
        logger.info(f"Персонаж ID={persona_id} удален пользователем user_id={user_id}")
        return True, "Персонаж успешно удален."
    else:
        return False, "Не удалось удалить персонажа."

