"""
Инфраструктура для административных действий.
"""

from .admin import ADMIN_IDS, is_admin
from .personas import delete_persona

__all__ = ["ADMIN_IDS", "is_admin", "delete_persona"]

