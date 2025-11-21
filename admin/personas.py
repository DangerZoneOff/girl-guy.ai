"""
Операции над анкетами, доступные администраторам.
Работает только с БД.
"""

from __future__ import annotations

import os
from pers.database import delete_persona as db_delete_persona, get_persona_by_id
from pers.storage import delete_photo
from knops.api_persons import invalidate_cache

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


async def delete_persona(persona_id: int) -> bool:
    """
    Удаляет персонажа из БД и связанные ресурсы (фото).
    Возвращает True, если персонаж удалён.
    """
    # Получаем данные персонажа перед удалением
    persona = get_persona_by_id(persona_id)
    if not persona:
        return False
    
    # Удаляем фото (из облака или локально)
    photo_path = persona.get("photo_path")
    photo_url = persona.get("photo_url")
    owner_id = persona.get("owner_id")
    name = persona.get("name")
    import logging
    logger = logging.getLogger(__name__)
    if photo_path or photo_url:
        logger.info(f"Удаление фото: photo_path={photo_path}, photo_url={photo_url}, owner_id={owner_id}, name={name}")
        deleted = await delete_photo(photo_path, photo_url, owner_id, name)
        if deleted:
            logger.info(f"Фото успешно удалено: {photo_path or photo_url}")
        else:
            logger.warning(f"Не удалось удалить фото: {photo_path or photo_url}")
    else:
        logger.warning(f"photo_path и photo_url не найдены для persona_id={persona_id}")
    
    # Удаляем из БД
    removed = db_delete_persona(persona_id)
    
    # Очищаем кэш профилей после удаления
    invalidate_cache()
    return removed

