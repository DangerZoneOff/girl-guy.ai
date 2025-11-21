"""
Фоновый таск, который периодически синхронизирует заказы Tribute.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from aiogram import Bot

from .tribute_service import sync_paid_orders

logger = logging.getLogger(__name__)


def get_sync_interval() -> int:
    try:
        return max(30, int(os.getenv("TRIBUTE_SYNC_INTERVAL", "60")))
    except ValueError:
        return 60


def start_tribute_sync(bot: Bot) -> asyncio.Task:
    interval = get_sync_interval()
    logger.info("Tribute sync task запускается с интервалом %s секунд", interval)
    return asyncio.create_task(_run(bot, interval))


async def _run(bot: Bot, interval: int) -> None:
    while True:
        try:
            processed, skipped = await sync_paid_orders(bot)
            if processed:
                logger.info("Tribute sync: начислено %s заказов (пропущено %s)", processed, skipped)
        except Exception:
            logger.exception("Tribute sync error")
        await asyncio.sleep(interval)


