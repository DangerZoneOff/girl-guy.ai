"""
Пакет payments: логика пополнения токенов через Telegram Payments.
"""

from .handlers import register_payment_handlers

__all__ = ["register_payment_handlers"]


