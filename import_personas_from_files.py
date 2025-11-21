"""
Импорт персонажей из .py файлов в БД
"""
import os
import sys
import io
import importlib.util
from pathlib import Path
from dotenv import load_dotenv

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

load_dotenv()

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from pers.database import init_database, create_persona

BASE_DIR = Path(__file__).parent
USERS_DIR = BASE_DIR / "pers" / "users"

print("=== Импорт персонажей из файлов в БД ===\n")

# Инициализируем БД
init_database()

imported = 0
errors = 0

# Проходим по всем пользователям
for user_dir in USERS_DIR.iterdir():
    if not user_dir.is_dir() or user_dir.name.startswith('_'):
        continue
    
    user_id = int(user_dir.name)
    print(f"\nПользователь {user_id}:")
    
    # Ищем все .py файлы с профилями
    for py_file in user_dir.glob("*_profile.py"):
        try:
            # Загружаем модуль
            spec = importlib.util.spec_from_file_location("profile", py_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Ищем функцию get_*()
            func_name = None
            for name in dir(module):
                if name.startswith('get_') and callable(getattr(module, name)):
                    func_name = name
                    break
            
            if not func_name:
                print(f"  WARNING: {py_file.name}: функция get_* не найдена")
                errors += 1
                continue
            
            # Вызываем функцию
            get_func = getattr(module, func_name)
            persona_data = get_func()
            
            # Извлекаем данные
            name = persona_data.get('name', '')
            age = persona_data.get('age', 0)
            description = persona_data.get('description', '')
            character = persona_data.get('character')
            scene = persona_data.get('scene')
            photo_path = persona_data.get('photo', '')
            
            # Проверяем, есть ли уже такой персонаж
            from pers.database import get_personas_by_owner
            existing = get_personas_by_owner(user_id, include_public=False)
            exists = any(p['name'] == name for p in existing)
            
            if exists:
                print(f"  SKIP: {name}: уже существует, пропускаю")
                continue
            
            # Создаем персонажа
            persona_id = create_persona(
                owner_id=user_id,
                name=name,
                age=age,
                description=description,
                character=character,
                scene=scene,
                photo_path=photo_path,
                public=True  # Делаем публичными
            )
            
            print(f"  OK: {name}: создан (ID={persona_id})")
            imported += 1
            
        except Exception as e:
            print(f"  ERROR: {py_file.name}: ошибка - {e}")
            errors += 1
            import traceback
            traceback.print_exc()

print(f"\n=== Итого ===")
print(f"Импортировано: {imported}")
print(f"Ошибок: {errors}")

# Проверяем результат
from pers.database import get_public_personas
personas = get_public_personas()
print(f"\nПубличных персонажей в БД: {len(personas)}")

