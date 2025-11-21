"""
Проверка что реально в БД в облаке
"""
import os
import sqlite3
import tempfile
from dotenv import load_dotenv
import boto3

load_dotenv()

bucket_name = os.getenv("YANDEX_BUCKET")
access_key_id = os.getenv("YANDEX_ACCESS_KEY_ID")
secret_access_key = os.getenv("YANDEX_SECRET_ACCESS_KEY")
endpoint_url = os.getenv("YANDEX_ENDPOINT", "https://storage.yandexcloud.net")
region = os.getenv("YANDEX_REGION", "ru-central1")

print("=== Проверка БД в облаке ===\n")

s3_client = boto3.client(
    "s3",
    endpoint_url=endpoint_url,
    aws_access_key_id=access_key_id,
    aws_secret_access_key=secret_access_key,
    region_name=region,
)

# Проверяем personas.db в облаке
print("1. Проверка personas.db в облаке:")
try:
    # Получаем метаданные
    response = s3_client.head_object(Bucket=bucket_name, Key="databases/personas.db")
    size = response['ContentLength']
    print(f"   Размер: {size} байт")
    
    # Скачиваем и проверяем содержимое
    import tempfile
    tmp_path = tempfile.mktemp(suffix='.db')
    try:
        s3_client.download_file(bucket_name, "databases/personas.db", tmp_path)
        
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        
        # Таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"   Таблицы: {[t[0] for t in tables]}")
        
        # Количество персонажей
        cursor.execute("SELECT COUNT(*) FROM personas")
        total = cursor.fetchone()[0]
        print(f"   Всего персонажей: {total}")
        
        # Публичные
        cursor.execute("SELECT COUNT(*) FROM personas WHERE public = 1")
        public = cursor.fetchone()[0]
        print(f"   Публичных: {public}")
        
        # Примеры
        if total > 0:
            cursor.execute("SELECT id, name, owner_id, public FROM personas LIMIT 5")
            rows = cursor.fetchall()
            print("\n   Примеры:")
            for row in rows:
                print(f"     ID={row[0]}, name={row[1]}, owner={row[2]}, public={row[3]}")
        else:
            print("\n   ВНИМАНИЕ: БД в облаке ПУСТАЯ!")
        
        conn.close()
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass
        
except Exception as e:
    print(f"   Ошибка: {e}")
    import traceback
    traceback.print_exc()

# Проверяем users.db в облаке
print("\n2. Проверка users.db в облаке:")
try:
    response = s3_client.head_object(Bucket=bucket_name, Key="databases/users.db")
    size = response['ContentLength']
    print(f"   Размер: {size} байт")
except Exception as e:
    print(f"   Ошибка: {e}")

