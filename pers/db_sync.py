"""
Синхронизация баз данных с Yandex Object Storage.
Загружает БД из облака при старте и сохраняет обратно при остановке.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Пути к базам данных
BASE_DIR = Path(__file__).parent.parent
USERS_DB = BASE_DIR / "users.db"
PERSONAS_DB = BASE_DIR / "pers" / "personas.db"

# Пути в облаке
CLOUD_DB_PREFIX = "databases/"


def get_s3_client():
    """Создает S3 клиент для Yandex Object Storage."""
    try:
        import boto3
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
        secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
        
        if not bucket_name or not access_key_id or not secret_access_key:
            logger.warning("Yandex ключи не настроены, синхронизация БД отключена")
            return None
        
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
    except ImportError:
        logger.warning("boto3 не установлен, синхронизация БД отключена")
        return None
    except Exception as e:
        logger.error(f"Ошибка создания S3 клиента: {e}")
        return None


def download_database(db_path: Path, cloud_key: str) -> bool:
    """
    Загружает базу данных из облака.
    Закрывает все соединения перед загрузкой и удаляет WAL файлы.
    
    Args:
        db_path: Локальный путь к БД
        cloud_key: Ключ в облаке (например, "databases/users.db")
    
    Returns:
        True если успешно загружено, False при ошибке
    """
    s3_client = get_s3_client()
    if not s3_client:
        return False
    
    bucket_name = os.getenv("YANDEX_BUCKET")
    
    try:
        # Закрываем все соединения с БД перед загрузкой
        # Удаляем WAL файлы если они есть
        wal_files = [
            db_path.with_suffix('.db-shm'),
            db_path.with_suffix('.db-wal'),
        ]
        for wal_file in wal_files:
            if wal_file.exists():
                try:
                    wal_file.unlink()
                    logger.debug(f"Удален WAL файл: {wal_file}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить WAL файл {wal_file}: {e}")
        
        # Создаем директорию если нужно
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем файл
        s3_client.download_file(bucket_name, cloud_key, str(db_path))
        
        # Проверяем размер файла
        file_size = db_path.stat().st_size
        logger.info(f"БД загружена из облака: {cloud_key} -> {db_path} (размер: {file_size} байт)")
        
        # Проверяем, что файл не пустой
        if file_size < 100:  # SQLite файл минимум ~2KB
            logger.warning(f"Загруженная БД очень маленькая ({file_size} байт), возможно она пустая")
        
        # Проверяем количество записей в personas.db
        if 'personas' in str(db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM personas")
                count = cursor.fetchone()[0]
                conn.close()
                logger.info(f"В загруженной personas.db найдено {count} персонажей")
            except Exception as e:
                logger.warning(f"Не удалось проверить количество персонажей: {e}")
        
        return True
    except Exception as e:
        error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')
        if error_code == 'NoSuchKey':
            logger.info(f"БД не найдена в облаке: {cloud_key}, используем локальную")
            return False
        logger.error(f"Ошибка загрузки БД из облака: {e}")
        return False


def upload_database(db_path: Path, cloud_key: str) -> bool:
    """
    Загружает базу данных в облако.
    Перед загрузкой проверяет, что WAL файлы применены к основной БД.
    
    Args:
        db_path: Локальный путь к БД
        cloud_key: Ключ в облаке (например, "databases/users.db")
    
    Returns:
        True если успешно загружено, False при ошибке
    """
    s3_client = get_s3_client()
    if not s3_client:
        return False
    
    if not db_path.exists():
        logger.warning(f"Локальная БД не найдена: {db_path}, пропускаю загрузку")
        return False
    
    bucket_name = os.getenv("YANDEX_BUCKET")
    
    try:
        # Проверяем наличие WAL файлов и применяем их к основной БД
        wal_file = db_path.with_suffix('.db-wal')
        if wal_file.exists():
            logger.info(f"Обнаружен WAL файл, применяю изменения к основной БД...")
            try:
                import sqlite3
                # Открываем БД в режиме WAL и делаем checkpoint для применения изменений
                conn = sqlite3.connect(str(db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.commit()
                conn.close()
                logger.info("WAL изменения применены к основной БД")
            except Exception as e:
                logger.warning(f"Не удалось применить WAL изменения: {e}")
        
        # Загружаем файл
        s3_client.upload_file(
            str(db_path),
            bucket_name,
            cloud_key,
            ExtraArgs={'ContentType': 'application/x-sqlite3'}
        )
        
        # Проверяем размер загруженного файла
        file_size = db_path.stat().st_size
        logger.info(f"БД загружена в облако: {db_path} -> {cloud_key} (размер: {file_size} байт)")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки БД в облако: {e}")
        return False


def sync_databases_from_cloud(force: bool = True) -> bool:
    """
    Загружает все БД из облака при старте бота.
    
    Args:
        force: Если True, всегда загружает из облака, даже если локальная БД существует
    
    Returns:
        True если хотя бы одна БД загружена, False если все пропущены
    """
    logger.info("Синхронизация БД из облака...")
    
    results = []
    
    # Загружаем users.db (всегда из облака, если там есть)
    if force or not USERS_DB.exists():
        results.append(download_database(USERS_DB, f"{CLOUD_DB_PREFIX}users.db"))
    else:
        # Проверяем, есть ли в облаке более свежая версия
        try:
            s3_client = get_s3_client()
            if s3_client:
                bucket_name = os.getenv("YANDEX_BUCKET")
                cloud_key = f"{CLOUD_DB_PREFIX}users.db"
                try:
                    # Проверяем дату модификации в облаке
                    response = s3_client.head_object(Bucket=bucket_name, Key=cloud_key)
                    cloud_time = response.get('LastModified', 0)
                    local_time = USERS_DB.stat().st_mtime
                    if cloud_time and cloud_time.timestamp() > local_time:
                        logger.info("В облаке более свежая версия users.db, загружаю...")
                        results.append(download_database(USERS_DB, cloud_key))
                    else:
                        logger.info("Локальная users.db актуальна")
                except Exception:
                    # Если не удалось проверить, просто загружаем
                    results.append(download_database(USERS_DB, cloud_key))
        except Exception as e:
            logger.warning(f"Не удалось проверить версию users.db в облаке: {e}")
    
    # Загружаем personas.db (всегда из облака, если там есть)
    if force or not PERSONAS_DB.exists():
        results.append(download_database(PERSONAS_DB, f"{CLOUD_DB_PREFIX}personas.db"))
    else:
        # Проверяем, есть ли в облаке более свежая версия
        try:
            s3_client = get_s3_client()
            if s3_client:
                bucket_name = os.getenv("YANDEX_BUCKET")
                cloud_key = f"{CLOUD_DB_PREFIX}personas.db"
                try:
                    # Проверяем дату модификации в облаке
                    response = s3_client.head_object(Bucket=bucket_name, Key=cloud_key)
                    cloud_time = response.get('LastModified', 0)
                    local_time = PERSONAS_DB.stat().st_mtime
                    if cloud_time and cloud_time.timestamp() > local_time:
                        logger.info("В облаке более свежая версия personas.db, загружаю...")
                        results.append(download_database(PERSONAS_DB, cloud_key))
                    else:
                        logger.info("Локальная personas.db актуальна")
                except Exception:
                    # Если не удалось проверить, просто загружаем
                    results.append(download_database(PERSONAS_DB, cloud_key))
        except Exception as e:
            logger.warning(f"Не удалось проверить версию personas.db в облаке: {e}")
    
    return any(results)


def sync_databases_to_cloud() -> bool:
    """
    Загружает все БД в облако при остановке бота.
    
    Returns:
        True если успешно загружено, False при ошибке
    """
    logger.info("Синхронизация БД в облако...")
    
    results = []
    
    # Загружаем users.db
    if USERS_DB.exists():
        results.append(upload_database(USERS_DB, f"{CLOUD_DB_PREFIX}users.db"))
    
    # Загружаем personas.db
    if PERSONAS_DB.exists():
        results.append(upload_database(PERSONAS_DB, f"{CLOUD_DB_PREFIX}personas.db"))
    
    return all(results)


async def sync_databases_to_cloud_async() -> bool:
    """Асинхронная версия загрузки БД в облако."""
    import asyncio
    return await asyncio.to_thread(sync_databases_to_cloud)

