import time
from typing import List, Dict, Optional

from pers.database import get_public_personas, persona_to_dict

# Кэш для списка профилей (только метаданные, без загрузки фото)
_profiles_cache: Optional[List[Dict]] = None
_cache_timestamp: float = 0
CACHE_TTL = 60  # Время жизни кэша в секундах (1 минута)


def list_profiles(force_refresh: bool = False) -> List[Dict]:
    """
    Возвращает список всех ПУБЛИЧНЫХ персонажей из БД.
    Использует кэширование для оптимизации.
    
    Args:
        force_refresh: Если True, принудительно обновляет кэш
    """
    global _profiles_cache, _cache_timestamp
    
    current_time = time.time()
    
    # Проверяем кэш
    if (
        not force_refresh
        and _profiles_cache is not None
        and (current_time - _cache_timestamp) < CACHE_TTL
    ):
        return _profiles_cache
    
    # Загружаем публичные персонажи из БД
    personas = get_public_personas()
    profiles = [persona_to_dict(row) for row in personas]
    
    # Обновляем кэш
    _profiles_cache = profiles
    _cache_timestamp = current_time
    
    return profiles


def invalidate_cache() -> None:
    """Принудительно очищает кэш профилей."""
    global _profiles_cache, _cache_timestamp
    _profiles_cache = None
    _cache_timestamp = 0
