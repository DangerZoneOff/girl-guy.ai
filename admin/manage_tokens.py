"""
Утилита для ручного управления балансом токенов пользователей.
Используется для исправления ошибок в оплате и административных задач.
"""

from __future__ import annotations

import sys
import argparse
import logging

from SMS.database import init_database, get_db_connection
from SMS.tokens import get_token_balance, set_token_balance, add_tokens

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def show_balance(user_id: int) -> None:
    """Показывает баланс пользователя."""
    init_database()
    balance = get_token_balance(user_id)
    print(f"👤 User ID: {user_id}")
    print(f"💰 Токенов: {balance}")


def set_balance(user_id: int, amount: int) -> None:
    """Устанавливает баланс пользователя."""
    init_database()
    old_balance = get_token_balance(user_id)
    new_balance = set_token_balance(user_id, amount)
    print(f"👤 User ID: {user_id}")
    print(f"📊 Старый баланс: {old_balance}")
    print(f"✅ Новый баланс: {new_balance}")


def add_balance(user_id: int, amount: int) -> None:
    """Добавляет токены пользователю."""
    init_database()
    old_balance = get_token_balance(user_id)
    new_balance = add_tokens(user_id, amount)
    print(f"👤 User ID: {user_id}")
    print(f"📊 Старый баланс: {old_balance}")
    print(f"➕ Добавлено: {amount}")
    print(f"✅ Новый баланс: {new_balance}")


def list_users(limit: int = 20) -> None:
    """Показывает список пользователей с балансами."""
    init_database()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, tokens, updated_at 
            FROM token_balances 
            ORDER BY updated_at DESC 
            LIMIT ?
            """,
            (limit,)
        )
        
        rows = cursor.fetchall()
        if not rows:
            print("Пользователей не найдено")
            return
        
        print(f"📋 Последние {len(rows)} пользователей:\n")
        print(f"{'User ID':<15} {'Токены':<10} {'Обновлено':<20}")
        print("-" * 50)
        for row in rows:
            print(f"{row['user_id']:<15} {row['tokens']:<10} {row['updated_at']:<20}")


def search_user(query: str) -> None:
    """Ищет пользователя по ID или части ID."""
    init_database()
    
    try:
        user_id = int(query)
        show_balance(user_id)
    except ValueError:
        # Поиск по части ID
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, tokens FROM token_balances WHERE user_id LIKE ? LIMIT 10",
                (f"%{query}%",)
            )
            rows = cursor.fetchall()
            if not rows:
                print(f"Пользователи с ID содержащим '{query}' не найдены")
                return
            
            print(f"🔍 Найдено пользователей: {len(rows)}\n")
            for row in rows:
                print(f"  User ID: {row['user_id']}, Токены: {row['tokens']}")


def main():
    """Основная функция CLI."""
    parser = argparse.ArgumentParser(
        description="Управление балансом токенов пользователей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Показать баланс пользователя
  python -m admin.manage_tokens show 123456789
  
  # Установить баланс
  python -m admin.manage_tokens set 123456789 100
  
  # Добавить токены
  python -m admin.manage_tokens add 123456789 50
  
  # Список пользователей
  python -m admin.manage_tokens list
  
  # Поиск пользователя
  python -m admin.manage_tokens search 123456
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Команды')
    
    # Команда show
    show_parser = subparsers.add_parser('show', help='Показать баланс пользователя')
    show_parser.add_argument('user_id', type=int, help='Telegram User ID')
    
    # Команда set
    set_parser = subparsers.add_parser('set', help='Установить баланс')
    set_parser.add_argument('user_id', type=int, help='Telegram User ID')
    set_parser.add_argument('amount', type=int, help='Количество токенов')
    
    # Команда add
    add_parser = subparsers.add_parser('add', help='Добавить токены')
    add_parser.add_argument('user_id', type=int, help='Telegram User ID')
    add_parser.add_argument('amount', type=int, help='Количество токенов для добавления')
    
    # Команда list
    list_parser = subparsers.add_parser('list', help='Список пользователей')
    list_parser.add_argument('--limit', type=int, default=20, help='Количество записей (по умолчанию 20)')
    
    # Команда search
    search_parser = subparsers.add_parser('search', help='Поиск пользователя')
    search_parser.add_argument('query', type=str, help='User ID или часть ID для поиска')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'show':
            show_balance(args.user_id)
        elif args.command == 'set':
            set_balance(args.user_id, args.amount)
        elif args.command == 'add':
            add_balance(args.user_id, args.amount)
        elif args.command == 'list':
            list_users(args.limit)
        elif args.command == 'search':
            search_user(args.query)
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

