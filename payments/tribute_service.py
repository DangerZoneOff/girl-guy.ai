"""
Бизнес-логика начисления токенов по заказам Tribute.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Tuple

from aiogram import Bot

from SMS.tokens import add_tokens, get_token_balance

from .products import iter_token_packs
from .tribute_api import list_product_orders
from .tribute_orders_store import mark_processed, was_processed

logger = logging.getLogger(__name__)


def _extract_tg_id(order: Dict[str, any]) -> Optional[int]:
    candidate_fields = [
        "telegram_id",
        "telegramID",
        "telegramId",
        "tg_id",
        "tgId",
    ]
    for field in candidate_fields:
        if field in order and order[field]:
            try:
                return int(order[field])
            except (TypeError, ValueError):
                continue
    buyer = order.get("buyer") or order.get("user") or {}
    for field in candidate_fields:
        if field in buyer and buyer[field]:
            try:
                return int(buyer[field])
            except (TypeError, ValueError):
                continue
    return None


async def sync_paid_orders(bot: Bot) -> Tuple[int, int]:
    processed = 0
    skipped = 0
    for pack in iter_token_packs():
        if not pack.product_id:
            continue
        try:
            orders = await list_product_orders(pack.product_id, status="paid")
        except Exception:
            logger.exception("Не удалось загрузить заказы для товара %s", pack.product_id)
            continue

        for order in orders:
            order_id = order.get("id") or order.get("uuid")
            if not order_id:
                skipped += 1
                continue
            storage_id = f"{pack.product_id}:{order_id}"
            if was_processed(storage_id):
                continue

            tg_id = _extract_tg_id(order)
            if not tg_id:
                logger.warning("Заказ %s (product %s) без Telegram ID", order_id, pack.product_id)
                mark_processed(storage_id, status="no_tg_id")
                skipped += 1
                continue

            add_tokens(tg_id, pack.tokens)
            balance = get_token_balance(tg_id)
            mark_processed(storage_id, status="paid", tokens=pack.tokens)
            processed += 1

            try:
                await bot.send_message(
                    tg_id,
                    f"⭐️ Tribute: +{pack.tokens} токенов\nТекущий баланс: {balance}",
                )
            except Exception as exc:
                logger.warning("Не удалось отправить сообщение пользователю %s: %s", tg_id, exc)

    return processed, skipped


