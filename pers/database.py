"""
SQLite база данных для хранения персонажей (Personas).
Полностью совместима с архитектурой users.db.
Использует connection pool, WAL-режим и параметризованные запросы.
"""

from __future__ import annotations

import sqlite3
import os
import logging
import threading
import queue
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Путь к БД: создается в той же папке, где лежит этот файл
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "personas.db"

# Настройки connection pool (как в users.db)
POOL_SIZE = 5
POOL_TIMEOUT = 10.0

# Thread-safe пул соединений
_connection_pool: Optional[queue.Queue] = None
_pool_lock = threading.Lock()
_pool_initialized = False


def _create_connection() -> sqlite3.Connection:
    """Создает новое соединение с БД с оптимальными настройками."""
    # Создаем папку, если её нет
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    
    # Оптимизации для производительности (WAL режим)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")
    
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
                logger.error(f"Ошибка при создании соединения для пула personas: {e}")
        
        _pool_initialized = True
        logger.info(f"Инициализирован connection pool для personas.db размером {POOL_SIZE}")


def close_all_connections() -> None:
    """Закрывает все соединения из пула (для корректного бекапа)."""
    global _connection_pool, _pool_initialized
    
    if not _pool_initialized or not _connection_pool:
        return
    
    with _pool_lock:
        if not _connection_pool:
            return
        
        closed_count = 0
        while True:
            try:
                conn = _connection_pool.get_nowait()
                try:
                    conn.close()
                    closed_count += 1
                except Exception as e:
                    logger.warning(f"Ошибка при закрытии соединения personas: {e}")
            except queue.Empty:
                break
        
        _connection_pool = None
        _pool_initialized = False
        
        if closed_count > 0:
            logger.info(f"Закрыто {closed_count} соединений personas.db")


@contextmanager
def get_db_connection(timeout: float = 10.0):
    """
    Контекстный менеджер для работы с БД.
    Гарантирует возврат соединения в пул и выполнение commit.
    """
    _init_pool()
    
    conn = None
    try:
        try:
            conn = _connection_pool.get(timeout=POOL_TIMEOUT)
        except queue.Empty:
            logger.warning("Пул personas пуст, создается временное соединение")
            conn = _create_connection()
        
        # Проверка здоровья соединения
        try:
            conn.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            logger.warning("Соединение personas мертво, пересоздание")
            try:
                conn.close()
            except:
                pass
            conn = _create_connection()
        
        yield conn
        
        # ВАЖНО: Явный commit для сохранения изменений
        try:
            conn.commit()
        except Exception as commit_error:
            logger.error(f"Ошибка при commit в personas.db: {commit_error}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Ошибка БД personas: {e}")
        raise
    finally:
        if conn:
            try:
                _connection_pool.put_nowait(conn)
            except queue.Full:
                conn.close()
            except Exception as e:
                logger.warning(f"Ошибка возврата в пул: {e}")
                try:
                    conn.close()
                except:
                    pass


def _load_database_from_cloud() -> None:
    """Загружает personas.db из облака, если локальной нет."""
    if DB_PATH.exists():
        return
    
    try:
        import boto3
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
        secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
        
        if not bucket_name or not access_key_id or not secret_access_key:
            return
        
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        cloud_key = "databases/personas.db"
        
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
        
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        s3_client.download_file(bucket_name, cloud_key, str(DB_PATH))
        logger.info("personas.db загружена из облака")
    except Exception as e:
        logger.warning(f"Не удалось загрузить personas.db: {e}")


def init_database() -> None:
    """Инициализирует структуру таблиц."""
    _load_database_from_cloud()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Основная таблица
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                description TEXT NOT NULL,
                character TEXT,
                scene TEXT,
                photo_path TEXT NOT NULL,
                photo_url TEXT,
                public BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner_id, name)
            )
        """)
        
        # Безопасное добавление новых колонок (миграции)
        migrations = [
            "ALTER TABLE personas ADD COLUMN initial_scene TEXT",
            "ALTER TABLE personas ADD COLUMN photo_file_id TEXT",
            "ALTER TABLE personas ADD COLUMN chat_count INTEGER DEFAULT 0"
        ]
        
        for migration in migrations:
            try:
                cursor.execute(migration)
            except sqlite3.OperationalError:
                # Колонка уже существует, игнорируем ошибку
                pass
        
        # Создание индексов
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_personas_owner_id ON personas(owner_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_personas_public ON personas(public)")
        
        logger.info("База данных personas.db успешно инициализирована")


# ==========================================
# Функции работы с данными
# ==========================================

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
    """Создает нового персонажа."""
    # Убедимся, что БД инициализирована (быстрая проверка)
    if not _pool_initialized:
        init_database()

    with get_db_connection() as conn:
        cursor = conn.cursor()
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
        logger.info(f"Создан персонаж ID={persona_id} для пользователя {owner_id}")
        return persona_id


def get_persona_by_id(persona_id: int) -> Optional[Dict[str, Any]]:
    """Получает данные персонажа по ID."""
    if not _pool_initialized:
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
    Возвращает список персонажей.
    Если include_public=True, возвращает своих + публичных.
    """
    if not _pool_initialized:
        init_database()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if include_public:
            query = """
                SELECT * FROM personas 
                WHERE owner_id = ? OR public = 1
                ORDER BY public DESC, name ASC
            """
            params = (owner_id,)
        else:
            query = """
                SELECT * FROM personas 
                WHERE owner_id = ?
                ORDER BY name ASC
            """
            params = (owner_id,)
            
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


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
    """Обновляет данные существующего персонажа."""
    if not _pool_initialized:
        init_database()

    updates = []
    params = []
    reset_file_id = False
    
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
        reset_file_id = True
    if photo_url is not None:
        updates.append("photo_url = ?")
        params.append(photo_url)
        reset_file_id = True
    
    # Если фото изменилось, сбрасываем cached file_id
    if reset_file_id:
        updates.append("photo_file_id = NULL")
        
    # Прямое обновление file_id (например, после отправки в Telegram)
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
        query = f"UPDATE personas SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        return cursor.rowcount > 0


def delete_persona(persona_id: int) -> bool:
    """Удаляет персонажа."""
    if not _pool_initialized:
        init_database()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM personas WHERE id = ?", (persona_id,))
        return cursor.rowcount > 0


def increment_persona_chat_count(persona_id: int) -> bool:
    """Увеличивает счетчик использований персонажа (популярность)."""
    if not _pool_initialized:
        init_database()
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE personas 
            SET chat_count = COALESCE(chat_count, 0) + 1 
            WHERE id = ?
        """, (persona_id,))
        return cursor.rowcount > 0


def get_public_personas() -> List[Dict[str, Any]]:
    """Возвращает список публичных персонажей, отсортированных по популярности."""
    if not _pool_initialized:
        init_database()
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM personas 
            WHERE public = 1 
            ORDER BY chat_count DESC, name ASC
        """)
        return [dict(row) for row in cursor.fetchall()]


def persona_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper для преобразования строки БД в формат, ожидаемый старыми частями кода.
    """
    return {
        "id": row["id"],
        "name": row["name"],
        "age": row["age"],
        "description": row["description"],
        "character": row.get("character"),
        "scene": row.get("scene"),
        "initial_scene": row.get("initial_scene"),
        "photo": row["photo_url"] or row["photo_path"],
        "photo_file_id": row.get("photo_file_id"),
        "owner_id": row["owner_id"],
        "public": bool(row["public"]),
        "chat_count": row.get("chat_count", 0)
    }

__all__ = [
    "init_database", 
    "create_persona", 
    "get_persona_by_id", 
    "get_personas_by_owner", 
    "update_persona", 
    "delete_persona",
    "increment_persona_chat_count",
    "get_public_personas",
    "persona_to_dict",
    "DB_PATH"
]