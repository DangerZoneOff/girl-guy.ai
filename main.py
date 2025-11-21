"""
Простой Telegram бот на aiogram.
"""

import asyncio
import contextlib
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from knops.handlers_gender import register_gender_handlers
from knops.handlers_menu import register_menu_handlers
from createpers.handlers_wizard import register_wizard_handlers
from ai.handlers_chat import register_chat_handlers
from payments import register_payment_handlers
from payments.stars_sync import start_stars_sync
from premium.handlers import register_premium_handlers
from refferals import register_referral_handlers, init_referrals
from refferals.constants import set_bot_username


async def _start_bot() -> None:
    load_dotenv()
    set_bot_username(os.getenv("TELEGRAM_BOT_USERNAME"))
    logging.basicConfig(level=logging.INFO)
    
    # Синхронизация БД из облака при старте
    try:
        from pers.db_sync import sync_databases_from_cloud
        sync_databases_from_cloud()
    except Exception as e:
        logging.warning(f"Не удалось синхронизировать БД из облака: {e}")
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env")
    bot = Bot(token=bot_token)
    dp = Dispatcher()

    await init_referrals(bot)

    register_gender_handlers(dp)
    register_menu_handlers(dp)
    register_payment_handlers(dp)
    register_chat_handlers(dp)
    register_wizard_handlers(dp)
    register_premium_handlers(dp)
    register_referral_handlers(dp)

    # Запускаем синхронизатор оплаты в Telegram Stars (опционально, если используется внешний API)
    stars_task = start_stars_sync(bot)
    
    # Очищаем временные файлы в облаке при старте бота (в фоне, не блокируем запуск)
    async def cleanup_on_start():
        try:
            from pers.storage import cleanup_temp_files_yandex
            deleted = await cleanup_temp_files_yandex()
            if deleted > 0:
                logging.info(f"Очищено {deleted} временных файлов в облаке при старте")
        except Exception as e:
            logging.debug(f"Не удалось очистить временные файлы при старте: {e}")
    
    asyncio.create_task(cleanup_on_start())
    
    # Периодическая синхронизация БД в облако (каждые 30 минут)
    async def periodic_db_sync():
        try:
            from pers.db_sync import sync_databases_to_cloud_async
            while True:
                await asyncio.sleep(1800)  # 30 минут
                await sync_databases_to_cloud_async()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Ошибка периодической синхронизации БД: {e}")
    
    sync_task = asyncio.create_task(periodic_db_sync())

    logging.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        # Синхронизация БД в облако при остановке
        try:
            from pers.db_sync import sync_databases_to_cloud_async
            await sync_databases_to_cloud_async()
        except Exception as e:
            logging.error(f"Не удалось синхронизировать БД в облако: {e}")
        
        if stars_task:
            stars_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stars_task
        
        if sync_task:
            sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sync_task


def main():
    asyncio.run(_start_bot())


if __name__ == "__main__":
    main()
