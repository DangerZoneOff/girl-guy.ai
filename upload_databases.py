"""
Скрипт для загрузки баз данных в Yandex Object Storage.
Запускайте на вашем компьютере для первоначальной загрузки БД.
"""

import os
import boto3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Пути к базам данных
BASE_DIR = Path(__file__).parent
USERS_DB = BASE_DIR / "users.db"
PERSONAS_DB = BASE_DIR / "pers" / "personas.db"

# Настройки Yandex Object Storage
BUCKET_NAME = os.getenv("YANDEX_BUCKET")
ACCESS_KEY_ID = os.getenv("YANDEX_ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("YANDEX_SECRET_ACCESS_KEY")
REGION = os.getenv("YANDEX_REGION", "ru-central1")
ENDPOINT_URL = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")

# Путь в облаке
CLOUD_PREFIX = "databases/"


def upload_db(local_path: Path, cloud_key: str):
    """Загружает БД в облако."""
    if not local_path.exists():
        print(f"Файл не найден: {local_path}")
        return False
    
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=ENDPOINT_URL,
            aws_access_key_id=ACCESS_KEY_ID,
            aws_secret_access_key=SECRET_ACCESS_KEY,
            region_name=REGION,
        )
        
        s3_client.upload_file(
            str(local_path),
            BUCKET_NAME,
            cloud_key,
            ExtraArgs={'ContentType': 'application/x-sqlite3'}
        )
        
        print(f"Загружено: {local_path.name} -> {cloud_key}")
        return True
    except Exception as e:
        print(f"Ошибка загрузки {local_path.name}: {e}")
        return False


def main():
    import sys
    import io
    
    # Устанавливаем UTF-8 для вывода
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    if not all([BUCKET_NAME, ACCESS_KEY_ID, SECRET_ACCESS_KEY]):
        print("Ошибка: YANDEX_BUCKET, YANDEX_ACCESS_KEY_ID и YANDEX_SECRET_ACCESS_KEY должны быть в .env")
        return
    
    print("Загрузка баз данных в Yandex Object Storage...")
    print(f"Бакет: {BUCKET_NAME}")
    print()
    
    results = []
    
    # Загружаем users.db
    if USERS_DB.exists():
        results.append(upload_db(USERS_DB, f"{CLOUD_PREFIX}users.db"))
    else:
        print(f"Файл не найден: {USERS_DB}")
    
    # Загружаем personas.db
    if PERSONAS_DB.exists():
        results.append(upload_db(PERSONAS_DB, f"{CLOUD_PREFIX}personas.db"))
    else:
        print(f"Файл не найден: {PERSONAS_DB}")
    
    print()
    if all(results):
        print("Все базы данных успешно загружены в облако!")
    elif any(results):
        print("Некоторые базы данных загружены")
    else:
        print("Не удалось загрузить базы данных")


if __name__ == "__main__":
    main()

