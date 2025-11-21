"""
Хранилище черновиков персонажей в SQLite.
Позволяет сохранять черновики между сессиями и перезапусками бота.
Использует параметризованные запросы для защиты от SQL инъекций.
"""

from __future__ import annotations

import sqlite3
import json
import os
import logging
from typing import Optional
from contextlib import contextmanager
from .wizard import PersonaDraft

logger = logging.getLogger(__name__)

# БД в папке pers для единообразия
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "pers", "wizard_drafts.db")


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД черновиков"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка БД черновиков: {e}")
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Инициализирует базу данных для черновиков"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Используем параметризованный запрос (безопасно!)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                user_id INTEGER PRIMARY KEY,
                draft_data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # commit выполняется автоматически контекстным менеджером


def save_draft(user_id: int, draft: PersonaDraft) -> None:
    """
    Сохраняет черновик в базу данных.
    Использует параметризованные запросы для защиты от SQL инъекций.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        draft_json = json.dumps(draft.to_dict(), ensure_ascii=False)
        # Параметризованный запрос - безопасно!
        cursor.execute("""
            INSERT OR REPLACE INTO drafts (user_id, draft_data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, draft_json))
        # commit выполняется автоматически контекстным менеджером
        logger.info(f"Черновик сохранен для user_id={user_id}")


def load_draft(user_id: int) -> Optional[PersonaDraft]:
    """
    Загружает черновик из базы данных.
    Использует параметризованные запросы для защиты от SQL инъекций.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Параметризованный запрос - безопасно!
        cursor.execute("SELECT draft_data FROM drafts WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        try:
            draft_dict = json.loads(row[0])
            return PersonaDraft.from_dict(draft_dict)
        except Exception as e:
            logger.error(f"Ошибка загрузки черновика: {e}")
            return None


def delete_draft(user_id: int) -> None:
    """
    Удаляет черновик из базы данных.
    Использует параметризованные запросы для защиты от SQL инъекций.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Параметризованный запрос - безопасно!
        cursor.execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))
        # commit выполняется автоматически контекстным менеджером
        logger.info(f"Черновик удален для user_id={user_id}")

