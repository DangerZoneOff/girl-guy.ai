"""
SQLite база данных для токенов, платежей и профилей пользователей.
Единая база для всех пользовательских данных.
Использует connection pool для оптимизации производительности.
"""

from __future__ import annotations

import sqlite3
import os
import logging
import threading
import queue
from typing import Optional, Dict, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Путь к БД в корне проекта
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "users.db"

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
        # Явно делаем commit перед возвратом соединения в пул
        # Это критично для сохранения изменений в WAL режиме
        # В WAL режиме commit должен быть явным для гарантии записи
        try:
            conn.commit()
        except Exception as commit_error:
            logger.error(f"Ошибка при commit: {commit_error}")
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


def _load_database_from_cloud() -> None:
    """
    Загружает users.db из Yandex Object Storage, если локальной нет.
    """
    if DB_PATH.exists():
        logger.debug("users.db уже существует локально, пропускаю загрузку из облака")
        return
    
    try:
        import boto3
        import os
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
        secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
        
        if not bucket_name or not access_key_id or not secret_access_key:
            logger.debug("Yandex ключи не настроены, пропускаю загрузку users.db из облака")
            return
        
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        cloud_key = "databases/users.db"
        
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
        
        # Создаем директорию если нужно
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем файл
        s3_client.download_file(bucket_name, cloud_key, str(DB_PATH))
        
        file_size = DB_PATH.stat().st_size
        logger.info(f"users.db загружена из облака (размер: {file_size} байт)")
    except Exception as e:
        error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')
        if error_code == 'NoSuchKey':
            logger.info("users.db не найдена в облаке, будет создана новая")
        else:
            logger.warning(f"Не удалось загрузить users.db из облака: {e}")


def init_database() -> None:
    """
    Инициализирует базу данных и создает таблицы.
    Вызывается автоматически при первом использовании.
    Загружает БД из облака, если локальной нет.
    """
    # Загружаем из облака перед инициализацией
    _load_database_from_cloud()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Включаем WAL режим для параллельных операций
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            result = cursor.fetchone()
            logger.info(f"Режим журнала БД: {result[0] if result else 'unknown'}")
        except Exception as e:
            logger.warning(f"Не удалось установить WAL режим: {e}")
        
        # Таблица токенов пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_balances (
                user_id INTEGER PRIMARY KEY,
                tokens INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица обработанных платежей в Stars
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stars_orders (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                status TEXT NOT NULL,
                tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица профилей пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                reg_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица реферальных привязок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_relations (
                invited_user_id INTEGER PRIMARY KEY,
                referrer_id INTEGER NOT NULL,
                rewarded INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_referral_referrer_id
            ON referral_relations(referrer_id)
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stars_orders_user_id 
            ON stars_orders(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stars_orders_status 
            ON stars_orders(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stars_orders_created 
            ON stars_orders(created_at)
        """)
        
        # commit выполняется автоматически контекстным менеджером
        logger.info("База данных users.db инициализирована")


__all__ = ["get_db_connection", "init_database", "DB_PATH"]

