"""
Тест синхронизации БД - проверяет что происходит при загрузке
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
PERSONAS_DB = BASE_DIR / "pers" / "personas.db"

print("=== Тест синхронизации БД ===\n")

# 1. Проверяем БД ДО синхронизации
print("1. БД ДО синхронизации:")
if PERSONAS_DB.exists():
    size_before = PERSONAS_DB.stat().st_size
    print(f"   Размер: {size_before} байт")
    
    conn = sqlite3.connect(str(PERSONAS_DB))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM personas")
    count_before = cursor.fetchone()[0]
    print(f"   Персонажей: {count_before}")
    conn.close()
else:
    print("   БД не существует")
    size_before = 0
    count_before = 0

# 2. Синхронизируем
print("\n2. Синхронизация из облака...")
try:
    from pers.db_sync import sync_databases_from_cloud
    result = sync_databases_from_cloud(force=True)
    print(f"   Результат: {result}")
except Exception as e:
    print(f"   Ошибка: {e}")
    import traceback
    traceback.print_exc()

# 3. Проверяем БД ПОСЛЕ синхронизации
print("\n3. БД ПОСЛЕ синхронизации:")
if PERSONAS_DB.exists():
    size_after = PERSONAS_DB.stat().st_size
    print(f"   Размер: {size_after} байт (было: {size_before})")
    
    conn = sqlite3.connect(str(PERSONAS_DB))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM personas")
    count_after = cursor.fetchone()[0]
    print(f"   Персонажей: {count_after} (было: {count_before})")
    
    # Публичные
    cursor.execute("SELECT COUNT(*) FROM personas WHERE public = 1")
    public_after = cursor.fetchone()[0]
    print(f"   Публичных: {public_after}")
    
    # Примеры
    if count_after > 0:
        cursor.execute("SELECT id, name, owner_id, public FROM personas LIMIT 3")
        rows = cursor.fetchall()
        print("\n   Примеры:")
        for row in rows:
            print(f"     ID={row[0]}, name={row[1]}, owner={row[2]}, public={row[3]}")
    
    conn.close()
else:
    print("   БД не существует после синхронизации!")

# 4. Проверяем что в облаке
print("\n4. Проверка облака:")
try:
    from pers.db_sync import get_s3_client
    s3_client = get_s3_client()
    if s3_client:
        bucket_name = os.getenv("YANDEX_BUCKET")
        response = s3_client.head_object(Bucket=bucket_name, Key="databases/personas.db")
        cloud_size = response['ContentLength']
        print(f"   Размер в облаке: {cloud_size} байт")
        
        # Скачиваем временно и проверяем
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            s3_client.download_file(bucket_name, "databases/personas.db", tmp.name)
            tmp_conn = sqlite3.connect(tmp.name)
            tmp_cursor = tmp_conn.cursor()
            tmp_cursor.execute("SELECT COUNT(*) FROM personas")
            cloud_count = tmp_cursor.fetchone()[0]
            tmp_cursor.execute("SELECT COUNT(*) FROM personas WHERE public = 1")
            cloud_public = tmp_cursor.fetchone()[0]
            tmp_conn.close()
            os.unlink(tmp.name)
            
            print(f"   Персонажей в облаке: {cloud_count}")
            print(f"   Публичных в облаке: {cloud_public}")
    else:
        print("   S3 клиент не создан")
except Exception as e:
    print(f"   Ошибка: {e}")
    import traceback
    traceback.print_exc()

