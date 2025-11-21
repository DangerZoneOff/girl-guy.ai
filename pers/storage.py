"""
Управление хранением фотографий персонажей.
Поддерживает локальное хранение и облачные сервисы (S3, Cloudinary и т.д.).
"""

from __future__ import annotations

import os
import hashlib
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Настройки хранения
STORAGE_TYPE = os.getenv("STORAGE_TYPE", "local")  # local, s3, cloudinary, yandex
PERS_DIR = os.path.dirname(__file__)
USERS_DIR = os.path.join(PERS_DIR, "users")


def normalize_character_name(character_name: str) -> str:
    """
    Нормализует имя персонажа для использования в путях и ключах.
    Убирает пробелы, приводит к нижнему регистру, заменяет спецсимволы.
    Используется везде для консистентности.
    
    Args:
        character_name: Исходное имя персонажа
    
    Returns:
        Нормализованное имя
    """
    import re
    # Убираем пробелы и заменяем на подчеркивания
    safe_name = character_name.strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
    # Приводим к нижнему регистру (работает с кириллицей в Python 3)
    safe_name = safe_name.lower()
    # Оставляем только буквы (включая кириллицу), цифры, дефисы, подчеркивания и точки
    # Используем UNICODE флаг для поддержки кириллицы
    safe_name = re.sub(r'[^\w\-_.]', '_', safe_name, flags=re.UNICODE)
    return safe_name


def get_photo_path(user_id: int, character_name: str, extension: str = "jpg") -> str:
    """
    Генерирует безопасный путь для сохранения фото.
    Использует хеш имени для предотвращения конфликтов.
    """
    safe_name = character_name.replace(" ", "_").lower()
    # Добавляем хеш для уникальности
    name_hash = hashlib.md5(safe_name.encode()).hexdigest()[:8]
    filename = f"photo_{safe_name}_{name_hash}.{extension}"
    
    user_dir = os.path.join(USERS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    return os.path.join(user_dir, filename)


def save_photo_local(file_data: bytes, user_id: int, character_name: str) -> str:
    """
    Сохраняет фото локально на диск.
    
    Returns:
        Относительный путь к файлу (для БД)
    """
    photo_path = get_photo_path(user_id, character_name)
    
    with open(photo_path, "wb") as f:
        f.write(file_data)
    
    # Возвращаем относительный путь от корня проекта
    rel_path = os.path.relpath(photo_path, os.path.dirname(PERS_DIR))
    logger.info(f"Фото сохранено локально: {rel_path}")
    return rel_path.replace("\\", "/")


async def upload_photo_cloudinary(file_data: bytes, user_id: int, character_name: str) -> Optional[str]:
    """
    Загружает фото в Cloudinary (требует установки cloudinary).
    
    Returns:
        URL загруженного фото или None при ошибке
    """
    try:
        import cloudinary
        import cloudinary.uploader
        
        # Настройки из переменных окружения
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        )
        
        safe_name = character_name.replace(" ", "_").lower()
        result = cloudinary.uploader.upload(
            file_data,
            folder=f"personas/{user_id}",
            public_id=safe_name,
            resource_type="image",
        )
        
        url = result.get("secure_url") or result.get("url")
        logger.info(f"Фото загружено в Cloudinary: {url}")
        return url
    except ImportError:
        logger.error("Cloudinary не установлен. pip install cloudinary")
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки в Cloudinary: {e}")
        return None


async def upload_photo_s3(file_data: bytes, user_id: int, character_name: str) -> Optional[str]:
    """
    Загружает фото в AWS S3 (требует установки boto3).
    
    Returns:
        URL загруженного фото или None при ошибке
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        
        bucket_name = os.getenv("AWS_S3_BUCKET")
        if not bucket_name:
            logger.error("AWS_S3_BUCKET не указан в переменных окружения")
            return None
        
        safe_name = character_name.replace(" ", "_").lower()
        key = f"personas/{user_id}/{safe_name}.jpg"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=file_data,
            ContentType="image/jpeg",
            ACL="public-read",  # Или "private" для приватных фото
        )
        
        # Генерируем публичный URL
        url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        logger.info(f"Фото загружено в S3: {url}")
        return url
    except ImportError:
        logger.error("boto3 не установлен. pip install boto3")
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки в S3: {e}")
        return None


async def upload_photo_yandex(file_data: bytes, user_id: int, character_name: str) -> Optional[str]:
    """
    Загружает фото в Yandex Object Storage (требует установки boto3).
    Yandex Object Storage использует S3-совместимый API.
    
    Returns:
        URL загруженного фото или None при ошибке
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
        secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
        
        if not bucket_name or not access_key_id or not secret_access_key:
            logger.error("YANDEX_BUCKET, YANDEX_ACCESS_KEY_ID и YANDEX_SECRET_ACCESS_KEY должны быть указаны")
            return None
        
        # Yandex Object Storage endpoint
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        
        # Создаем S3-совместимый клиент для Yandex
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
        
        # Нормализуем имя: используем единую функцию нормализации
        safe_name = normalize_character_name(character_name)
        key = f"personas/{user_id}/{safe_name}.jpg"
        
        logger.info(f"Нормализация имени: '{character_name}' -> '{safe_name}'")
        logger.info(f"Загрузка фото в Yandex с ключом: {key}")
        
        # Загружаем файл
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=file_data,
                ContentType="image/jpeg",
                ACL="public-read",  # Для публичного доступа
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == '403' or 'AccessDenied' in str(e):
                logger.error(f"Нет доступа к bucket '{bucket_name}'. Проверьте:")
                logger.error("1. Правильность YANDEX_ACCESS_KEY_ID и YANDEX_SECRET_ACCESS_KEY")
                logger.error("2. Роль ключа должна быть storage.editor или storage.admin")
                logger.error("3. Ключ должен иметь доступ к bucket 'girl-guy-personas'")
                logger.error(f"Ошибка: {error_message}")
            elif error_code == '404' or 'NoSuchBucket' in str(e):
                logger.error(f"Bucket '{bucket_name}' не найден. Проверьте название bucket в Yandex Cloud Console")
            else:
                logger.error(f"Ошибка загрузки в Yandex: {error_code} - {error_message}")
            return None
        
        # Генерируем публичный URL
        # Yandex Object Storage URL формат: https://{bucket}.storage.yandexcloud.net/{key}
        url = f"https://{bucket_name}.storage.yandexcloud.net/{key}"
        logger.info(f"Фото загружено в Yandex Object Storage: {url}")
        
        # Очищаем временные файлы после успешной загрузки (в фоне, не блокируем)
        # Используем try-except, чтобы не прерывать загрузку при ошибках очистки
        try:
            import asyncio
            # Создаем задачу очистки в фоне, не ждем результата
            asyncio.create_task(cleanup_temp_files_yandex())
        except Exception as e:
            logger.debug(f"Не удалось запустить очистку временных файлов: {e}")
        
        return url
    except ImportError:
        logger.error("boto3 не установлен. pip install boto3")
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки в Yandex Object Storage: {e}")
        logger.error("Проверьте настройки в .env файле и права доступа ключа")
        return None


async def save_photo(
    file_data: bytes,
    user_id: int,
    character_name: str,
    storage_type: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Сохраняет фото в зависимости от типа хранилища.
    
    Args:
        file_data: Байты файла
        user_id: ID пользователя
        character_name: Имя персонажа
        storage_type: Тип хранилища (local, s3, cloudinary, yandex)
    
    Returns:
        Tuple[photo_path, photo_url]
        - photo_path: Локальный путь (для локального хранения) или ключ (для облака)
        - photo_url: URL фото (для облачного хранения) или None
    """
    storage = storage_type or STORAGE_TYPE
    
    if storage == "local":
        photo_path = save_photo_local(file_data, user_id, character_name)
        return photo_path, None
    
    elif storage == "cloudinary":
        photo_url = await upload_photo_cloudinary(file_data, user_id, character_name)
        if photo_url:
            return f"cloudinary:{user_id}/{character_name}", photo_url
        # Fallback на локальное хранение при ошибке
        logger.warning("Cloudinary недоступен, сохраняю локально")
        photo_path = save_photo_local(file_data, user_id, character_name)
        return photo_path, None
    
    elif storage == "s3":
        photo_url = await upload_photo_s3(file_data, user_id, character_name)
        if photo_url:
            return f"s3:{user_id}/{character_name}", photo_url
        # Fallback на локальное хранение при ошибке
        logger.warning("S3 недоступен, сохраняю локально")
        photo_path = save_photo_local(file_data, user_id, character_name)
        return photo_path, None
    
    elif storage == "yandex":
        logger.info(f"Попытка загрузки фото в Yandex Object Storage для user_id={user_id}, character_name={character_name}")
        photo_url = await upload_photo_yandex(file_data, user_id, character_name)
        if photo_url:
            logger.info(f"Успешно загружено в Yandex: {photo_url}")
            # Сохраняем photo_path в формате "yandex:{user_id}/{safe_name}" для единообразия
            # Используем ту же нормализацию, что и при загрузке
            safe_name = normalize_character_name(character_name)
            photo_path = f"yandex:{user_id}/{safe_name}"
            logger.info(f"photo_path сохранен в формате: {photo_path}")
            return photo_path, photo_url
        # Fallback на локальное хранение при ошибке
        logger.error("Yandex Object Storage недоступен или произошла ошибка, сохраняю локально")
        logger.error("Проверьте: YANDEX_BUCKET, YANDEX_ACCESS_KEY_ID, YANDEX_SECRET_ACCESS_KEY установлены в .env")
        photo_path = save_photo_local(file_data, user_id, character_name)
        return photo_path, None
    
    else:
        logger.warning(f"Неизвестный тип хранилища: {storage}, использую local")
        photo_path = save_photo_local(file_data, user_id, character_name)
        return photo_path, None


async def delete_photo_yandex(photo_path: str, photo_url: str = None, user_id: int = None, character_name: str = None) -> bool:
    """
    Удаляет фото из Yandex Object Storage.
    
    Args:
        photo_path: Путь в формате "yandex:{user_id}/{character_name}" или локальный путь
        photo_url: URL фото (приоритетный способ определения ключа)
        user_id: ID пользователя (для формирования ключа, если нет URL)
        character_name: Имя персонажа (для формирования ключа, если нет URL)
    
    Returns:
        True если удалено успешно, False при ошибке
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
        secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
        
        if not bucket_name or not access_key_id or not secret_access_key:
            logger.error("Yandex ключи не настроены, не могу удалить фото из облака")
            return False
        
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
        
        # Определяем ключ для удаления (приоритет: photo_url > photo_path с "yandex:" > формирование из user_id и character_name)
        # Формат ключа всегда: personas/{user_id}/{safe_name}.jpg
        key = None
        
        if photo_url and "storage.yandexcloud.net/" in photo_url:
            # Извлекаем ключ из URL (самый надежный способ)
            # Формат URL: https://{bucket}.storage.yandexcloud.net/personas/{user_id}/{character_name}.jpg
            key = photo_url.split("storage.yandexcloud.net/")[1]
            logger.info(f"Ключ извлечен из URL: {key}")
        elif photo_path and photo_path.startswith("yandex:"):
            # Формат: "yandex:{user_id}/{safe_name}" (без расширения)
            key_part = photo_path.replace("yandex:", "")
            key = f"personas/{key_part}.jpg"
            logger.info(f"Ключ сформирован из photo_path: {key}")
        elif user_id and character_name:
            # Формируем ключ из user_id и character_name (как при сохранении)
            # ВАЖНО: используем ту же нормализацию, что и при сохранении
            safe_name = normalize_character_name(character_name)
            key = f"personas/{user_id}/{safe_name}.jpg"
            logger.info(f"Ключ сформирован из user_id и character_name: {key}")
        else:
            logger.error(f"Не могу определить ключ для удаления: photo_path={photo_path}, photo_url={photo_url}, user_id={user_id}, character_name={character_name}")
            return False
        
        # Удаляем объект из Yandex Object Storage
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=key)
            logger.info(f"Фото удалено из Yandex Object Storage: {key}")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(f"Фото уже не существует в Yandex: {key}")
                return True  # Считаем успехом, если уже удалено
            else:
                logger.error(f"Ошибка удаления из Yandex: {e}")
                return False
    except ImportError:
        logger.error("boto3 не установлен, не могу удалить фото из Yandex")
        return False
    except Exception as e:
        logger.error(f"Ошибка удаления фото из Yandex: {e}")
        return False


async def cleanup_temp_files_yandex() -> int:
    """
    Удаляет временные файлы из Yandex Object Storage.
    Ищет файлы с форматом имени: YYYY-MM-DD-HH-MM-SS-XXXXXXXX (дата-время-хеш)
    
    Returns:
        Количество удаленных файлов
    """
    try:
        import boto3
        import re
        from botocore.exceptions import ClientError
        from datetime import datetime, timedelta
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
        secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
        
        if not bucket_name or not access_key_id or not secret_access_key:
            logger.debug("Yandex ключи не настроены, пропускаю очистку временных файлов")
            return 0
        
        endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
        
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=os.getenv("YANDEX_REGION", "ru-central1"),
        )
        
        # Паттерн для временных файлов: YYYY-MM-DD-HH-MM-SS-XXXXXXXX
        # Например: 2025-11-19-18-59-59-187996DE3FCA8B89
        temp_file_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-[A-F0-9]{16}$')
        
        deleted_count = 0
        
        try:
            # Получаем список всех объектов в bucket
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    # Извлекаем имя файла (последняя часть пути)
                    filename = key.split('/')[-1]
                    # Убираем расширение для проверки
                    name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
                    
                    # Проверяем, соответствует ли имя паттерну временного файла
                    if temp_file_pattern.match(name_without_ext):
                        try:
                            # Удаляем файл
                            s3_client.delete_object(Bucket=bucket_name, Key=key)
                            deleted_count += 1
                            logger.info(f"Удален временный файл из Yandex: {key}")
                        except ClientError as e:
                            logger.warning(f"Не удалось удалить временный файл {key}: {e}")
        
        except ClientError as e:
            logger.error(f"Ошибка при очистке временных файлов в Yandex: {e}")
            return deleted_count
        
        if deleted_count > 0:
            logger.info(f"Очищено временных файлов в Yandex: {deleted_count}")
        
        return deleted_count
    
    except ImportError:
        logger.debug("boto3 не установлен, пропускаю очистку временных файлов")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при очистке временных файлов: {e}")
        return 0


async def delete_photo(photo_path: str, photo_url: str = None, user_id: int = None, character_name: str = None) -> bool:
    """
    Удаляет фото с диска или из облачного хранилища.
    
    Args:
        photo_path: Путь к фото (локальный или ключ облачного хранилища)
        photo_url: URL фото (для облачного хранилища, опционально)
    
    Returns:
        True если удалено успешно, False при ошибке
    """
    try:
        # Проверяем, хранится ли фото в Yandex Object Storage
        # Если есть photo_url с storage.yandexcloud.net или photo_path начинается с "yandex:"
        is_yandex = (
            photo_path.startswith("yandex:") or 
            (photo_url and "storage.yandexcloud.net" in photo_url)
        )
        
        if is_yandex:
            logger.info(f"Удаление фото из Yandex: photo_path={photo_path}, photo_url={photo_url}, user_id={user_id}, character_name={character_name}")
            return await delete_photo_yandex(photo_path, photo_url, user_id, character_name)
        elif photo_path.startswith("cloudinary:"):
            logger.info(f"Cloudinary фото не удаляется автоматически: {photo_path}")
            return True
        elif photo_path.startswith("s3:"):
            logger.info(f"S3 фото не удаляется автоматически: {photo_path}")
            return True
        
        # Локальный путь
        full_path = os.path.join(os.path.dirname(PERS_DIR), photo_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Фото удалено локально: {full_path}")
            return True
        logger.warning(f"Локальный файл не найден: {full_path}")
        return False
    except Exception as e:
        logger.error(f"Ошибка удаления фото: {e}")
        return False

