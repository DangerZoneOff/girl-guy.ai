"""Проверка содержимого БД"""
import sqlite3

# Проверяем personas.db
try:
    conn = sqlite3.connect('pers/personas.db')
    cursor = conn.cursor()
    
    # Количество персонажей
    cursor.execute('SELECT COUNT(*) FROM personas')
    count = cursor.fetchone()[0]
    print(f"Всего персонажей в БД: {count}")
    
    # Публичные персонажи
    cursor.execute('SELECT COUNT(*) FROM personas WHERE public = 1')
    public_count = cursor.fetchone()[0]
    print(f"Публичных персонажей: {public_count}")
    
    # Примеры
    cursor.execute('SELECT id, name, owner_id, public FROM personas LIMIT 10')
    rows = cursor.fetchall()
    print("\nПримеры персонажей:")
    for row in rows:
        print(f"  ID={row[0]}, name={row[1]}, owner={row[2]}, public={row[3]}")
    
    conn.close()
except Exception as e:
    print(f"Ошибка: {e}")

# Проверяем users.db
try:
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM token_balances')
    count = cursor.fetchone()[0]
    print(f"\nПользователей в users.db: {count}")
    
    conn.close()
except Exception as e:
    print(f"Ошибка проверки users.db: {e}")

