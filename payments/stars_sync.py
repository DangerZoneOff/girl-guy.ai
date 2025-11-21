"""
Фоновый таск для синхронизации оплаченных платежей в Telegram Stars.

Примечание: Синхронизация используется только если включён внешний API.
Основной поток платежей обрабатывается через обработчики PreCheckoutQuery
и SuccessfulPayment в handlers.py.
"""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot

from .stars_service import sync_paid_stars_payments

logger = logging.getLogger(__name__)

USE_EXTERNAL_API = os.getenv("STARS_USE_EXTERNAL_API", "false").lower() == "true"


def get_sync_interval() -> int:
    """Возвращает интервал синхронизации в секундах."""
    return int(os.getenv("STARS_SYNC_INTERVAL", "60"))


async def _run(bot: Bot, interval: int) -> None:
    """Основной цикл синхронизации."""
    while True:
        try:
            await asyncio.sleep(interval)
            processed, skipped = await sync_paid_stars_payments(bot)
            if processed > 0 or skipped > 0:
                logger.info(
                    "Stars sync: обработано %d платежей, пропущено %d",
                    processed,
                    skipped,
                )
        except asyncio.CancelledError:
            logger.info("Stars sync task отменён")
            raise
        except Exception as e:
            logger.error("Stars sync error", exc_info=True)


def start_stars_sync(bot: Bot) -> asyncio.Task | None:
    """
    Запускает фоновый таск синхронизации оплаченных платежей в звёздах.
    
    Возвращает None, если синхронизация не требуется (платежи обрабатываются
    напрямую через обработчики Bot API).
    """
    if not USE_EXTERNAL_API:
        logger.info("Stars sync отключён: платежи обрабатываются через обработчики Bot API")
        return None
    
    interval = get_sync_interval()
    logger.info("Stars sync task запускается с интервалом %s секунд", interval)
    return asyncio.create_task(_run(bot, interval))

