from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .handlers import register_referral_handlers
from .service import process_referral_payload
from .constants import BOT_USERNAME, set_bot_username

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)


async def init_referrals(bot: "Bot") -> None:
    """Получает username бота из API, если он не задан вручную."""
    if BOT_USERNAME:
        return
    try:
        me = await bot.get_me()
        set_bot_username(me.username)
        logger.info("Referral module: bot username set to @%s", me.username)
    except Exception as e:
        logger.warning("Referral module: failed to fetch bot username: %s", e)


__all__ = [
    "register_referral_handlers",
    "process_referral_payload",
    "init_referrals",
]

