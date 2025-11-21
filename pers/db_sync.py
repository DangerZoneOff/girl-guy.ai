"""
Принудительная синхронизация баз данных с Yandex Object Storage.
Всегда загружает БД из облака при старте и всегда сохраняет в облако при остановке.
"""

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
            return None, None
        
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
        
        return s3_client, bucket_name
    except ImportError:
        logger.warning("boto3 не установлен, синхронизация БД отключена")
        return None, None
    except Exception as e:
        logger.error(f"Ошибка создания S3 клиента: {e}")
        return None, None


def download_database(db_path: Path, cloud_key: str) -> bool:
    """
    Загружает базу данных из облака.
    Удаляет старые WAL файлы перед загрузкой.
    
    Args:
        db_path: Локальный путь к БД
        cloud_key: Ключ в облаке (например, "databases/users.db")
    
    Returns:
        True если успешно загружено, False при ошибке
    """
    s3_client, bucket_name = get_s3_client()
    if not s3_client or not bucket_name:
        return False
    
    try:
        # Закрываем все соединения перед загрузкой
        db_name = db_path.name
        if db_name == "users.db":
            try:
                from SMS.database import close_all_connections
                close_all_connections()
            except Exception:
                pass
        elif db_name == "personas.db":
            try:
                from pers.database import close_all_connections
                close_all_connections()
            except Exception:
                pass
        
        # Удаляем старые WAL файлы если есть
        wal_file = db_path.with_suffix('.db-wal')
        shm_file = db_path.with_suffix('.db-shm')
        
        if wal_file.exists():
            try:
                wal_file.unlink()
                logger.debug(f"Удален старый WAL файл: {wal_file}")
            except Exception as e:
                logger.warning(f"Не удалось удалить WAL файл: {e}")
        
        if shm_file.exists():
            try:
                shm_file.unlink()
                logger.debug(f"Удален старый SHM файл: {shm_file}")
            except Exception as e:
                logger.warning(f"Не удалось удалить SHM файл: {e}")
        
        # Создаем директорию если нужно
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Загружаем файл
        s3_client.download_file(bucket_name, cloud_key, str(db_path))
        
        file_size = db_path.stat().st_size
        logger.info(f"БД загружена из облака: {cloud_key} -> {db_path} (размер: {file_size} байт)")
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
    Закрывает все соединения и применяет WAL изменения перед загрузкой.
    
    Args:
        db_path: Локальный путь к БД
        cloud_key: Ключ в облаке (например, "databases/users.db")
    
    Returns:
        True если успешно загружено, False при ошибке
    """
    s3_client, bucket_name = get_s3_client()
    if not s3_client or not bucket_name:
        return False
    
    # Если БД не существует, создаем пустую
    if not db_path.exists():
        logger.warning(f"Локальная БД не найдена: {db_path}, создаю пустую")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.close()
        except Exception as e:
            logger.error(f"Не удалось создать пустую БД: {e}")
            return False
    
    try:
        import time
        import sqlite3
        
        # Шаг 1: Закрываем все соединения из пула
        db_name = db_path.name
        if db_name == "users.db":
            try:
                from SMS.database import close_all_connections
                close_all_connections()
                logger.info("Закрыты все соединения с users.db")
            except Exception as e:
                logger.warning(f"Не удалось закрыть соединения с users.db: {e}")
        elif db_name == "personas.db":
            try:
                from pers.database import close_all_connections
                close_all_connections()
                logger.info("Закрыты все соединения с personas.db")
            except Exception as e:
                logger.warning(f"Не удалось закрыть соединения с personas.db: {e}")
        
        # Шаг 2: Ждем завершения всех операций
        time.sleep(1.0)
        
        # Шаг 3: Применяем WAL изменения несколько раз для надежности
        wal_file = db_path.with_suffix('.db-wal')
        shm_file = db_path.with_suffix('.db-shm')
        
        # Делаем checkpoint несколько раз, пока WAL файл не исчезнет
        max_attempts = 5
        for attempt in range(max_attempts):
            if not wal_file.exists() and not shm_file.exists():
                break
            
            try:
                # Открываем соединение в режиме EXCLUSIVE для гарантированного checkpoint
                conn = sqlite3.connect(str(db_path), timeout=10.0)
                # TRUNCATE более агрессивный - применяет все изменения и удаляет WAL
                result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                checkpoint_result = result.fetchone()
                conn.commit()
                conn.close()
                
                # Проверяем результат checkpoint
                if checkpoint_result:
                    logger.debug(f"Checkpoint attempt {attempt + 1}: {checkpoint_result}")
                
                # Небольшая задержка между попытками
                time.sleep(0.3)
                
            except Exception as e:
                logger.warning(f"Ошибка при checkpoint (попытка {attempt + 1}): {e}")
                time.sleep(0.5)
        
        # Шаг 4: Принудительно удаляем WAL файлы если они остались
        if wal_file.exists():
            try:
                wal_file.unlink()
                logger.info("WAL файл принудительно удален")
            except Exception as e:
                logger.warning(f"Не удалось удалить WAL файл: {e}")
        
        if shm_file.exists():
            try:
                shm_file.unlink()
                logger.info("SHM файл принудительно удален")
            except Exception as e:
                logger.warning(f"Не удалось удалить SHM файл: {e}")
        
        # Шаг 5: Проверяем размер и содержимое БД перед загрузкой
        file_size_before = db_path.stat().st_size
        logger.info(f"Размер БД перед загрузкой: {file_size_before} байт")
        
        # Проверяем содержимое БД
        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            cursor = conn.cursor()
            
            # Проверяем таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logger.info(f"Таблицы в БД: {[t[0] for t in tables]}")
            
            # Проверяем количество записей в основных таблицах
            if db_name == "users.db":
                try:
                    cursor.execute("SELECT COUNT(*) FROM token_balances")
                    count = cursor.fetchone()[0]
                    logger.info(f"Записей в token_balances: {count}")
                except:
                    pass
            elif db_name == "personas.db":
                try:
                    cursor.execute("SELECT COUNT(*) FROM personas")
                    count = cursor.fetchone()[0]
                    logger.info(f"Записей в personas: {count}")
                except:
                    pass
            
            conn.close()
        except Exception as e:
            logger.warning(f"Не удалось проверить содержимое БД: {e}")
        
        if file_size_before < 3000:
            logger.warning(f"ВНИМАНИЕ: БД очень маленькая ({file_size_before} байт), возможно пустая!")
        
        # Шаг 6: Загружаем файл в облако
        s3_client.upload_file(
            str(db_path),
            bucket_name,
            cloud_key,
            ExtraArgs={'ContentType': 'application/x-sqlite3'}
        )
        
        file_size_after = db_path.stat().st_size
        logger.info(f"БД загружена в облако: {db_path} -> {cloud_key} (размер: {file_size_after} байт)")
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки БД в облако: {e}")
        return False


def sync_databases_from_cloud() -> bool:
    """
    Принудительно загружает все БД из облака при старте бота.
    
    Returns:
        True если хотя бы одна БД загружена, False если все пропущены
    """
    logger.info("Загрузка БД из облака...")
    
    results = []
    
    # Всегда загружаем users.db из облака
    logger.info("Загружаю users.db из облака...")
    results.append(download_database(USERS_DB, f"{CLOUD_DB_PREFIX}users.db"))
    
    # Всегда загружаем personas.db из облака
    logger.info("Загружаю personas.db из облака...")
    results.append(download_database(PERSONAS_DB, f"{CLOUD_DB_PREFIX}personas.db"))
    
    return any(results)


def sync_databases_to_cloud() -> bool:
    """
    Принудительно загружает все БД в облако при остановке бота.
    
    Returns:
        True если успешно загружено, False при ошибке
    """
    logger.info("Сохранение БД в облако...")
    
    results = []
    
    # Всегда загружаем users.db в облако
    logger.info("Сохраняю users.db в облако...")
    results.append(upload_database(USERS_DB, f"{CLOUD_DB_PREFIX}users.db"))
    
    # Всегда загружаем personas.db в облако
    logger.info("Сохраняю personas.db в облако...")
    results.append(upload_database(PERSONAS_DB, f"{CLOUD_DB_PREFIX}personas.db"))
    
    return all(results)


async def sync_databases_to_cloud_async() -> bool:
    """Асинхронная версия загрузки БД в облако."""
    import asyncio
    return await asyncio.to_thread(sync_databases_to_cloud)
