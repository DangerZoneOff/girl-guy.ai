"""
Бизнес-логика начисления токенов по оплатам в Telegram Stars.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from aiogram import Bot

from SMS.tokens import add_tokens, get_token_balance

from .stars_api import list_paid_payments
from .stars_orders_store import mark_processed, was_processed

logger = logging.getLogger(__name__)


async def sync_paid_stars_payments(bot: Bot) -> Tuple[int, int]:
    """
    Синхронизирует оплаченные платежи в звёздах и начисляет токены.
    Возвращает (processed_count, skipped_count).
    """
    try:
        payments = await list_paid_payments(limit=100, offset=0)
    except Exception as e:
        logger.error("Не удалось загрузить оплаченные платежи в звёздах: %s", e)
        return 0, 0

    processed = 0
    skipped = 0

    for payment in payments:
        payment_id = str(payment.get("payment_id") or payment.get("id") or "")
        if not payment_id:
            skipped += 1
            continue

        if was_processed(payment_id):
            continue

        # Извлекаем Telegram ID пользователя
        user_id = payment.get("user_id") or payment.get("telegram_id") or payment.get("tg_id")
        if not user_id:
            logger.warning("Stars payment %s без user_id", payment_id)
            mark_processed(payment_id, status="no_user_id", user_id=None)
            skipped += 1
            continue

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            logger.warning("Stars payment %s имеет некорректный user_id: %s", payment_id, user_id)
            mark_processed(payment_id, status="bad_user_id", user_id=None)
            skipped += 1
            continue

        # Количество звёзд = количество токенов (1 звезда = 1 токен)
        amount_stars = payment.get("amount_stars") or payment.get("amount") or payment.get("stars")
        if not amount_stars:
            logger.warning("Stars payment %s без amount_stars", payment_id)
            mark_processed(payment_id, status="no_amount", user_id=user_id_int)
            skipped += 1
            continue

        try:
            tokens = int(amount_stars)
        except (TypeError, ValueError):
            logger.warning("Stars payment %s имеет некорректный amount_stars: %s", payment_id, amount_stars)
            mark_processed(payment_id, status="bad_amount", user_id=user_id_int)
            skipped += 1
            continue

        # Начисляем токены
        add_tokens(user_id_int, tokens)
        balance = get_token_balance(user_id_int)
        mark_processed(payment_id, status="paid", tokens=tokens, user_id=user_id_int)
        processed += 1

        try:
            await bot.send_message(
                user_id_int,
                f"⭐️ Оплата в звёздах: +{tokens} токенов\nТекущий баланс: {balance}",
            )
        except Exception as e:
            logger.warning("Не удалось отправить сообщение пользователю %s: %s", user_id_int, e)

    return processed, skipped

