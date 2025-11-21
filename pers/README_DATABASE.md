# 🗄️ База данных персонажей

## Безопасность

### ✅ Защита от SQL инъекций

Все запросы используют **параметризованные запросы** с плейсхолдерами `?`:

```python
# ✅ ПРАВИЛЬНО - параметризованный запрос
cursor.execute("SELECT * FROM personas WHERE id = ?", (persona_id,))

# ❌ НЕПРАВИЛЬНО - уязвимо к SQL инъекциям
cursor.execute(f"SELECT * FROM personas WHERE id = {persona_id}")
```

**Почему это безопасно:**
- SQLite автоматически экранирует все специальные символы
- Параметры передаются отдельно от запроса
- Невозможно внедрить SQL код через пользовательский ввод

### 🔒 Дополнительные меры безопасности

1. **Валидация входных данных** - проверка типов и диапазонов
2. **Транзакции** - автоматический rollback при ошибках
3. **Индексы** - для быстрого поиска без уязвимостей
4. **Ограничения БД** - UNIQUE, NOT NULL, CHECK constraints

## Структура БД

### Таблица `personas`

```sql
CREATE TABLE personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,           -- ID владельца
    name TEXT NOT NULL,                   -- Имя персонажа
    age INTEGER NOT NULL,                 -- Возраст
    description TEXT NOT NULL,            -- Описание
    character TEXT,                       -- Характер (опционально)
    scene TEXT,                           -- Сцена (опционально)
    photo_path TEXT NOT NULL,             -- Путь к фото (локальный или ключ)
    photo_url TEXT,                       -- URL фото (для облачного хранения)
    public BOOLEAN DEFAULT 0,             -- Публичность
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(owner_id, name)                -- Один персонаж с таким именем у пользователя
);
```

### Индексы

- `idx_owner_id` - быстрый поиск по владельцу
- `idx_public` - быстрый поиск публичных персонажей
- `idx_owner_public` - комбинированный индекс

## Хранение фотографий

### Вариант 1: Локальное хранение (по умолчанию)

**Плюсы:**
- Бесплатно
- Быстро
- Не требует внешних сервисов

**Минусы:**
- Занимает место на диске
- Нет резервного копирования
- Медленнее для пользователей из других регионов

**Использование:**
```bash
# В .env или переменных окружения
STORAGE_TYPE=local
```

Фото сохраняются в: `pers/users/{user_id}/photo_{name}_{hash}.jpg`

### Вариант 2: Cloudinary

**Плюсы:**
- CDN для быстрой загрузки
- Автоматическая оптимизация изображений
- Бесплатный тариф (25GB)

**Минусы:**
- Требует регистрации
- Ограничения на бесплатном тарифе

**Настройка:**
```bash
# Установка
pip install cloudinary

# В .env
STORAGE_TYPE=cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### Вариант 3: AWS S3

**Плюсы:**
- Надежность
- Масштабируемость
- Гибкие настройки доступа

**Минусы:**
- Платно (но дешево)
- Требует настройки

**Настройка:**
```bash
# Установка
pip install boto3

# В .env
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your_bucket_name
```

### Вариант 4: Yandex Object Storage

**Плюсы:**
- Российский сервис (быстрая загрузка в РФ)
- S3-совместимый API
- Хорошие тарифы
- Надежность

**Минусы:**
- Требует регистрации в Yandex Cloud
- Нужна настройка

**Настройка:**
```bash
# Установка (используется тот же boto3)
pip install boto3

# В .env
STORAGE_TYPE=yandex
YANDEX_BUCKET=your-bucket-name
YANDEX_ACCESS_KEY_ID=your_access_key_id
YANDEX_SECRET_ACCESS_KEY=your_secret_access_key
YANDEX_REGION=ru-central1
# Опционально
YANDEX_ENDPOINT=https://storage.yandexcloud.net
```

**Как получить ключи доступа:**
1. Зайдите в [Yandex Cloud Console](https://console.cloud.yandex.ru/)
2. Создайте сервисный аккаунт
3. Назначьте роль `storage.editor` или `storage.admin`
4. Создайте статический ключ доступа
5. Скопируйте `Access Key ID` и `Secret Access Key`
6. Создайте bucket в Object Storage
7. Настройте публичный доступ (если нужен) через CORS и политики доступа

## Миграция данных

Если у вас уже есть персонажи в старом формате (Python модули), можно создать скрипт миграции:

```python
# Пример миграции (создать отдельный скрипт)
from pers.database import create_persona
from knops.api_persons import list_profiles

profiles = list_profiles()
for profile in profiles:
    create_persona(
        owner_id=profile.get("owner_id", 0),
        name=profile["name"],
        age=profile["age"],
        description=profile["description"],
        character=profile.get("character"),
        scene=profile.get("scene"),
        photo_path=profile["photo"],
        public=profile.get("public", False),
    )
```

## Использование

### Создание персонажа

```python
from pers.database import create_persona
from pers.storage import save_photo

# Сохраняем фото
photo_path, photo_url = await save_photo(file_data, user_id, "Имя")

# Создаем персонажа
persona_id = create_persona(
    owner_id=user_id,
    name="Имя",
    age=25,
    description="Описание",
    character="Характер",
    scene="Сцена",
    photo_path=photo_path,
    photo_url=photo_url,
    public=False,
)
```

### Получение персонажей

```python
from pers.database import get_personas_by_owner, get_public_personas

# Персонажи пользователя
my_personas = get_personas_by_owner(user_id, include_public=False)

# Публичные персонажи
public_personas = get_public_personas()
```

### Обновление персонажа

```python
from pers.database import update_persona

update_persona(
    persona_id=1,
    name="Новое имя",
    public=True,
)
```

## Резервное копирование

Рекомендуется регулярно делать бэкапы БД:

```bash
# Простое копирование файла
cp pers/personas.db pers/personas.db.backup

# Или через SQLite
sqlite3 pers/personas.db ".backup pers/personas.db.backup"
```

