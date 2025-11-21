"""
SQLite база данных для хранения персонажей.
Использует параметризованные запросы для защиты от SQL инъекций.
Использует connection pool для оптимизации производительности.
"""

from __future__ import annotations

import sqlite3
import os
import logging
import threading
import queue
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Путь к БД в папке pers
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "personas.db")

# Настройки connection pool
POOL_SIZE = 5  # Количество соединений в пуле
POOL_TIMEOUT = 10.0  # Таймаут ожидания соединения из пула

# Thread-safe пул соединений
_connection_pool: Optional[queue.Queue] = None
_pool_lock = threading.Lock()
_pool_initialized = False


def _create_connection() -> sqlite3.Connection:
    """Создает новое соединение с БД с оптимальными настройками."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    
    # Оптимизации для производительности
    conn.execute("PRAGMA journal_mode=WAL")  # WAL режим для параллельных операций
    conn.execute("PRAGMA synchronous=NORMAL")  # Баланс между скоростью и надежностью
    conn.execute("PRAGMA cache_size=-64000")  # 64MB кэш (отрицательное значение в KB)
    conn.execute("PRAGMA temp_store=MEMORY")  # Временные таблицы в памяти
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
    
    return conn


def _init_pool() -> None:
    """Инициализирует пул соединений."""
    global _connection_pool, _pool_initialized
    
    if _pool_initialized:
        return
    
    with _pool_lock:
        if _pool_initialized:
            return
        
        _connection_pool = queue.Queue(maxsize=POOL_SIZE)
        
        # Создаем начальные соединения
        for _ in range(POOL_SIZE):
            try:
                conn = _create_connection()
                _connection_pool.put(conn)
            except Exception as e:
                logger.error(f"Ошибка при создании соединения для пула: {e}")
        
        _pool_initialized = True
        logger.info(f"Инициализирован connection pool размером {POOL_SIZE}")


def close_all_connections() -> None:
    """
    Закрывает все соединения из пула.
    Используется перед загрузкой БД в облако для применения WAL изменений.
    """
    global _connection_pool, _pool_initialized
    
    if not _pool_initialized or not _connection_pool:
        return
    
    with _pool_lock:
        if not _connection_pool:
            return
        
        closed_count = 0
        # Закрываем все соединения из пула
        while True:
            try:
                conn = _connection_pool.get_nowait()
                try:
                    conn.close()
                    closed_count += 1
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии соединения: {e}")
            except queue.Empty:
                break
        
        _connection_pool = None
        _pool_initialized = False
        
        if closed_count > 0:
            logger.info(f"Закрыто {closed_count} соединений из пула")


@contextmanager
def get_db_connection(timeout: float = 10.0):
    """
    Контекстный менеджер для работы с БД с использованием connection pool.
    Автоматически возвращает соединение в пул после использования.
    
    Args:
        timeout: Таймаут ожидания разблокировки БД в секундах (по умолчанию 10)
    """
    _init_pool()
    
    conn = None
    try:
        # Получаем соединение из пула
        try:
            conn = _connection_pool.get(timeout=POOL_TIMEOUT)
        except queue.Empty:
            # Если пул пуст, создаем временное соединение
            logger.warning("Пул соединений пуст, создается временное соединение")
            conn = _create_connection()
        
        # Проверяем, что соединение живое
        try:
            conn.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            # Соединение мертво, создаем новое
            logger.warning("Соединение из пула мертво, создается новое")
            try:
                conn.close()
            except:
                pass
            conn = _create_connection()
        
        yield conn
        conn.commit()
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка БД: {e}")
        raise
    finally:
        if conn:
            # Возвращаем соединение в пул или закрываем, если пул переполнен
            try:
                _connection_pool.put_nowait(conn)
            except queue.Full:
                # Пул переполнен, закрываем соединение
                conn.close()
            except Exception as e:
                # Ошибка при возврате в пул, закрываем соединение
                logger.warning(f"Ошибка при возврате соединения в пул: {e}")
                try:
                    conn.close()
                except:
                    pass


def init_database() -> None:
    """
    Инициализирует базу данных и создает таблицы.
    Вызывается автоматически при первом использовании.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Включаем WAL режим для параллельных операций
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            result = cursor.fetchone()
            logger.info(f"Режим журнала БД: {result[0] if result else 'unknown'}")
        except Exception as e:
            logger.warning(f"Не удалось установить WAL режим: {e}")
        
        # Таблица персонажей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                description TEXT NOT NULL,
                character TEXT,
                scene TEXT,
                initial_scene TEXT,
                photo_path TEXT NOT NULL,
                photo_url TEXT,
                public BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_id, name)
            )
        """)
        
        # Добавляем поле initial_scene если его нет (для существующих БД)
        try:
            cursor.execute("ALTER TABLE personas ADD COLUMN initial_scene TEXT")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Добавляем поле photo_file_id для кэширования file_id от Telegram
        try:
            cursor.execute("ALTER TABLE personas ADD COLUMN photo_file_id TEXT")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Добавляем поле chat_count для подсчета популярности (количество запросов)
        try:
            cursor.execute("ALTER TABLE personas ADD COLUMN chat_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_owner_id ON personas(owner_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_public ON personas(public)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_owner_public ON personas(owner_id, public)
        """)
        
        # commit выполняется автоматически контекстным менеджером
        logger.info("База данных инициализирована")


def create_persona(
    owner_id: int,
    name: str,
    age: int,
    description: str,
    photo_path: str,
    character: Optional[str] = None,
    scene: Optional[str] = None,
    initial_scene: Optional[str] = None,
    photo_url: Optional[str] = None,
    public: bool = False,
) -> int:
    """
    Создает нового персонажа в БД.
    Использует параметризованные запросы для защиты от SQL инъекций.
    
    Returns:
        ID созданного персонажа
    """
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # ВСЕГДА используем параметризованные запросы (?) вместо форматирования строк
        cursor.execute("""
            INSERT INTO personas 
            (owner_id, name, age, description, character, scene, initial_scene, photo_path, photo_url, public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            owner_id,
            name,
            age,
            description,
            character,
            scene,
            initial_scene,
            photo_path,
            photo_url,
            1 if public else 0,
        ))
        persona_id = cursor.lastrowid
        logger.info(f"Создан персонаж ID={persona_id}, owner={owner_id}, name={name}")
        return persona_id


def get_persona_by_id(persona_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает персонажа по ID.
    Использует параметризованный запрос.
    """
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM personas WHERE id = ?", (persona_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def get_personas_by_owner(owner_id: int, include_public: bool = True) -> List[Dict[str, Any]]:
    """
    Получает всех персонажей пользователя.
    Использует параметризованный запрос.
    """
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if include_public:
            # Получаем персонажей пользователя ИЛИ публичных
            cursor.execute("""
                SELECT * FROM personas 
                WHERE owner_id = ? OR public = 1
                ORDER BY name
            """, (owner_id,))
        else:
            # Только персонажи пользователя
            cursor.execute("""
                SELECT * FROM personas 
                WHERE owner_id = ?
                ORDER BY name
            """, (owner_id,))
        
        return [dict(row) for row in cursor.fetchall()]


def get_public_personas() -> List[Dict[str, Any]]:
    """
    Получает всех публичных персонажей, отсортированных по популярности (количество запросов).
    """
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Сначала проверяем общее количество записей
        cursor.execute("SELECT COUNT(*) FROM personas")
        total_count = cursor.fetchone()[0]
        logger.debug(f"Всего персонажей в БД: {total_count}")
        
        # Проверяем публичных
        cursor.execute("SELECT COUNT(*) FROM personas WHERE public = 1")
        public_count = cursor.fetchone()[0]
        logger.debug(f"Публичных персонажей: {public_count}")
        
        # Получаем публичных персонажей
        cursor.execute("""
            SELECT * FROM personas 
            WHERE public = 1
            ORDER BY chat_count DESC, name ASC
        """)
        result = [dict(row) for row in cursor.fetchall()]
        
        if len(result) == 0 and total_count > 0:
            logger.warning(f"В БД есть {total_count} персонажей, но ни один не публичный!")
        
        return result


def update_persona(
    persona_id: int,
    name: Optional[str] = None,
    age: Optional[int] = None,
    description: Optional[str] = None,
    character: Optional[str] = None,
    scene: Optional[str] = None,
    initial_scene: Optional[str] = None,
    photo_path: Optional[str] = None,
    photo_url: Optional[str] = None,
    photo_file_id: Optional[str] = None,
    public: Optional[bool] = None,
) -> bool:
    """
    Обновляет данные персонажа.
    Использует параметризованные запросы и динамическое построение SET.
    """
    init_database()
    
    updates = []
    params = []
    reset_file_id = False  # Флаг для отслеживания необходимости сброса file_id
    
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if age is not None:
        updates.append("age = ?")
        params.append(age)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if character is not None:
        updates.append("character = ?")
        params.append(character)
    if scene is not None:
        updates.append("scene = ?")
        params.append(scene)
    if initial_scene is not None:
        updates.append("initial_scene = ?")
        params.append(initial_scene)
    if photo_path is not None:
        updates.append("photo_path = ?")
        params.append(photo_path)
        # При обновлении фото сбрасываем старый file_id, так как фото изменилось
        reset_file_id = True
    if photo_url is not None:
        updates.append("photo_url = ?")
        params.append(photo_url)
        # При обновлении фото сбрасываем старый file_id, так как фото изменилось
        reset_file_id = True
    if reset_file_id:
        updates.append("photo_file_id = NULL")
    if photo_file_id is not None:
        updates.append("photo_file_id = ?")
        params.append(photo_file_id)
    if public is not None:
        updates.append("public = ?")
        params.append(1 if public else 0)
    
    if not updates:
        return False
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(persona_id)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Параметризованный запрос с динамическим SET
        query = f"UPDATE personas SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        affected = cursor.rowcount
        logger.info(f"Обновлен персонаж ID={persona_id}, изменено строк: {affected}")
        return affected > 0


def delete_persona(persona_id: int) -> bool:
    """
    Удаляет персонажа по ID.
    Использует параметризованный запрос.
    """
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
        affected = cursor.rowcount
        logger.info(f"Удален персонаж ID={persona_id}, удалено строк: {affected}")
        return affected > 0


def set_persona_public(persona_id: int, public: bool) -> bool:
    """
    Устанавливает публичность персонажа.
    Использует параметризованный запрос.
    """
    return update_persona(persona_id, public=public)


def increment_persona_chat_count(persona_id: int) -> bool:
    """
    Увеличивает счетчик запросов (популярность) персонажа на 1.
    Используется при начале чата с персонажем.
    
    Returns:
        True если успешно обновлено, False если персонаж не найден
    """
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE personas 
            SET chat_count = COALESCE(chat_count, 0) + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (persona_id,))
        affected = cursor.rowcount
        if affected > 0:
            logger.debug(f"Увеличен счетчик запросов для persona_id={persona_id}")
        return affected > 0


def persona_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Преобразует строку БД в формат, совместимый со старым кодом.
    """
    return {
        "id": row["id"],
        "name": row["name"],
        "age": row["age"],
        "description": row["description"],
        "character": row.get("character"),
        "scene": row.get("scene"),
        "initial_scene": row.get("initial_scene"),
        "photo": row["photo_url"] or row["photo_path"],  # Приоритет URL над локальным путем
        "photo_file_id": row.get("photo_file_id"),  # file_id для кэширования в Telegram
        "owner_id": row["owner_id"],
        "public": bool(row["public"]),
        "chat_count": row.get("chat_count", 0) or 0,  # Количество запросов (популярность)
        "_module_file": None,  # Для совместимости со старым кодом
    }

