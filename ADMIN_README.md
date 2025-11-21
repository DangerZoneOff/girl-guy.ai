# Административные утилиты

## Управление балансом токенов

Для ручного изменения баланса токенов пользователей используйте утилиту `admin/manage_tokens.py`.

### Примеры использования:

```bash
# Показать баланс пользователя
python -m admin.manage_tokens show 123456789

# Установить точный баланс (например, при ошибке в оплате)
python -m admin.manage_tokens set 123456789 100

# Добавить токены к текущему балансу
python -m admin.manage_tokens add 123456789 50

# Показать список последних пользователей
python -m admin.manage_tokens list

# Поиск пользователя по ID
python -m admin.manage_tokens search 123456
```

### Типичные сценарии:

**Исправление ошибки в оплате:**
```bash
# Пользователь оплатил 100 токенов, но они не начислились
python -m admin.manage_tokens add 123456789 100
```

**Установка баланса вручную:**
```bash
# Установить точное количество токенов
python -m admin.manage_tokens set 123456789 200
```

## Прямая работа с базой данных

Если нужно быстро изменить данные напрямую в SQLite:

```bash
# Открыть базу данных
sqlite3 users.db

# Примеры SQL запросов:
# Показать баланс пользователя
SELECT * FROM token_balances WHERE user_id = 123456789;

# Изменить баланс
UPDATE token_balances SET tokens = 100 WHERE user_id = 123456789;

# Показать последние платежи
SELECT * FROM stars_orders ORDER BY created_at DESC LIMIT 10;
```

