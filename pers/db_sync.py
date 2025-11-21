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
        # Создаем директорию если нужно
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем файл
        s3_client.download_file(bucket_name, cloud_key, str(db_path))
        logger.info(f"БД загружена из облака: {cloud_key} -> {db_path}")
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
        # Загружаем файл
        s3_client.upload_file(
            str(db_path),
            bucket_name,
            cloud_key,
            ExtraArgs={'ContentType': 'application/x-sqlite3'}
        )
        logger.info(f"БД загружена в облако: {db_path} -> {cloud_key}")
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки БД в облако: {e}")
        return False


def sync_databases_from_cloud() -> bool:
    """
    Загружает все БД из облака при старте бота.
    
    Returns:
        True если хотя бы одна БД загружена, False если все пропущены
    """
    logger.info("Синхронизация БД из облака...")
    
    results = []
    
    # Загружаем users.db
    if USERS_DB.exists():
        logger.info("Локальная users.db существует, пропускаю загрузку из облака")
    else:
        results.append(download_database(USERS_DB, f"{CLOUD_DB_PREFIX}users.db"))
    
    # Загружаем personas.db
    if PERSONAS_DB.exists():
        logger.info("Локальная personas.db существует, пропускаю загрузку из облака")
    else:
        results.append(download_database(PERSONAS_DB, f"{CLOUD_DB_PREFIX}personas.db"))
    
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

