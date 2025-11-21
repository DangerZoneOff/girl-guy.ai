"""
Скрипт для проверки БД на сервере.
Запускайте в Cloud Shell на сервере.
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

print("=== Проверка БД на сервере ===\n")

# Пути
BASE_DIR = Path(__file__).parent
USERS_DB = BASE_DIR / "users.db"
PERSONAS_DB = BASE_DIR / "pers" / "personas.db"

print(f"Рабочая директория: {BASE_DIR}")
print(f"users.db существует: {USERS_DB.exists()}")
print(f"personas.db существует: {PERSONAS_DB.exists()}")

if USERS_DB.exists():
    size = USERS_DB.stat().st_size
    print(f"Размер users.db: {size} байт")
    
if PERSONAS_DB.exists():
    size = PERSONAS_DB.stat().st_size
    print(f"Размер personas.db: {size} байт\n")

# Проверяем personas.db
print("=== Проверка personas.db ===")
if PERSONAS_DB.exists():
    try:
        conn = sqlite3.connect(str(PERSONAS_DB))
        cursor = conn.cursor()
        
        # Проверяем таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Таблицы в БД: {[t[0] for t in tables]}")
        
        # Количество всех персонажей
        cursor.execute("SELECT COUNT(*) FROM personas")
        total = cursor.fetchone()[0]
        print(f"Всего персонажей: {total}")
        
        # Публичные персонажи
        cursor.execute("SELECT COUNT(*) FROM personas WHERE public = 1")
        public = cursor.fetchone()[0]
        print(f"Публичных персонажей: {public}")
        
        # Примеры
        if public > 0:
            cursor.execute("SELECT id, name, owner_id, public FROM personas WHERE public = 1 LIMIT 5")
            rows = cursor.fetchall()
            print("\nПримеры публичных персонажей:")
            for row in rows:
                print(f"  ID={row[0]}, name={row[1]}, owner={row[2]}, public={row[3]}")
        else:
            print("\nПубличных персонажей нет!")
            # Проверяем все персонажи
            cursor.execute("SELECT id, name, owner_id, public FROM personas LIMIT 5")
            rows = cursor.fetchall()
            if rows:
                print("Все персонажи (включая приватные):")
                for row in rows:
                    print(f"  ID={row[0]}, name={row[1]}, owner={row[2]}, public={row[3]}")
        
        conn.close()
    except Exception as e:
        print(f"Ошибка при проверке personas.db: {e}")
        import traceback
        traceback.print_exc()
else:
    print("personas.db не найдена!")

# Проверяем переменные окружения
print("\n=== Проверка переменных окружения ===")
env_vars = [
    "YANDEX_BUCKET",
    "YANDEX_ACCESS_KEY_ID",
    "YANDEX_SECRET_ACCESS_KEY",
    "YANDEX_REGION",
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        if "KEY" in var or "SECRET" in var:
            print(f"{var}: {'*' * 10} (установлен)")
        else:
            print(f"{var}: {value}")
    else:
        print(f"{var}: НЕ УСТАНОВЛЕН")

# Проверяем синхронизацию
print("\n=== Проверка синхронизации ===")
try:
    from pers.db_sync import get_s3_client, sync_databases_from_cloud
    
    s3_client = get_s3_client()
    if s3_client:
        print("S3 клиент создан успешно")
        
        bucket_name = os.getenv("YANDEX_BUCKET")
        if bucket_name:
            try:
                # Проверяем наличие файлов в облаке
                response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="databases/")
                if 'Contents' in response:
                    print(f"\nФайлы в облаке (databases/):")
                    for obj in response['Contents']:
                        print(f"  {obj['Key']} ({obj['Size']} байт)")
                else:
                    print("Файлы в databases/ не найдены в облаке!")
            except Exception as e:
                print(f"Ошибка при проверке облака: {e}")
    else:
        print("S3 клиент не создан (проверьте переменные окружения)")
        
    # Пробуем синхронизировать
    print("\nПопытка синхронизации из облака...")
    result = sync_databases_from_cloud(force=True)
    print(f"Результат синхронизации: {result}")
    
except Exception as e:
    print(f"Ошибка при проверке синхронизации: {e}")
    import traceback
    traceback.print_exc()

