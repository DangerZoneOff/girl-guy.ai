"""
Обработка пополнений через Telegram Stars.
"""

from __future__ import annotations

import json
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from SMS.tokens import add_tokens, get_token_balance
from .keyboards import get_token_packs_keyboard
from .products import get_pack_by_id
from .stars_orders_store import mark_processed, was_processed

logger = logging.getLogger(__name__)

PAY_HELP_CALLBACK = "pay:help"
STARS_PAY_PREFIX = "stars:pay:"


async def _send_topup_menu(message: Message) -> None:
    """Показывает меню пополнения баланса с выбором: токены или премиум."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Купить токены", callback_data="topup:tokens")
    builder.button(text="⭐ Купить премиум", callback_data="topup:premium")
    builder.adjust(1)  # По одной кнопке в ряд
    
    text = (
        "💰 <b>Пополнение баланса</b>\n\n"
        "Выбери, что хочешь купить:"
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


async def start_topup_via_command(message: Message) -> None:
    await _send_topup_menu(message)


async def start_topup_via_button(message: Message) -> None:
    await _send_topup_menu(message)


async def handle_topup_help(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "После оплаты в Telegram Stars бот автоматически начислит токены. "
        "1 звезда = 1 сообщение. Если баланс не обновился, напиши в поддержку.",
    )


async def handle_topup_choice(call: CallbackQuery, bot: Bot) -> None:
    """Обрабатывает выбор в меню пополнения баланса."""
    try:
        await call.answer()
    except Exception:
        pass  # Игнорируем ошибки ответа на callback
    
    if not call.data:
        logger.error("handle_topup_choice: call.data is None")
        if call.message:
            await call.message.answer("Ошибка: неверные данные.")
        return
    
    if not call.message:
        logger.error("handle_topup_choice: call.message is None")
        return
    
    logger.info(f"handle_topup_choice вызван с data={call.data}")
    
    choice = call.data.split(":")[-1] if ":" in call.data else call.data
    logger.info(f"handle_topup_choice: выбор={choice}")
    
    try:
        if choice == "tokens":
            # Показываем меню с пакетами токенов
            text = (
                "💰 <b>Пополнение токенов</b>\n\n"
                "Оплата в Telegram Stars. 1 звезда = 1 сообщение.\n"
                "Выбери пакет ниже, оплати звёздами, и токены автоматически поступят на баланс."
            )
            await call.message.answer(text, reply_markup=get_token_packs_keyboard(), parse_mode="HTML")
        elif choice == "premium":
            # Показываем меню премиум - call.message это уже Message объект
            logger.info("handle_topup_choice: показываем меню премиум")
            from premium.handlers import show_premium_menu
            await show_premium_menu(call.message)
        else:
            logger.warning(f"Неизвестный выбор в handle_topup_choice: {choice}, data={call.data}")
            await call.message.answer("Неверный выбор. Попробуй снова.")
    except Exception as e:
        logger.error(f"Ошибка в handle_topup_choice: {e}", exc_info=True)
        if call.message:
            await call.message.answer("Произошла ошибка. Попробуй позже.")


async def handle_stars_payment_callback(call: CallbackQuery, bot: Bot) -> None:
    """Обрабатывает нажатие на кнопку оплаты в звёздах."""
    await call.answer()
    parts = (call.data or "").split(":")
    pack_id = parts[-1] if len(parts) >= 3 else None
    pack = get_pack_by_id(pack_id)
    if not pack:
        await call.message.answer("Не удалось определить пакет. Попробуй снова.")
        return

    try:
        # Создаём payload с информацией о пакете
        payload_data = {
            "pack_id": pack.pack_id,
            "tokens": pack.tokens,
            "user_id": call.from_user.id,
        }
        payload = json.dumps(payload_data)

        # Создаём кнопку оплаты
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Оплатить {int(pack.price_amount)} ⭐", pay=True)

        # Отправляем счёт на оплату
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=pack.title,
            description=pack.description,
            payload=payload,
            provider_token="",  # Для Telegram Stars должен быть пустой
            currency="XTR",  # XTR - валюта Telegram Stars
            prices=[LabeledPrice(label=pack.title, amount=int(pack.price_amount))],
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error("Ошибка при создании платежа в звёздах: %s", e, exc_info=True)
        await call.message.answer(
            "Не удалось создать платёж. Попробуй позже или обратись в поддержку."
        )


async def handle_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
    """Обрабатывает предчекаут-запрос перед оплатой."""
    try:
        # Проверяем payload
        payload_data = json.loads(pre_checkout_query.invoice_payload)
        payment_type = payload_data.get("type")
        
        # Обработка премиум подписки
        if payment_type == "premium":
            from premium.handlers import handle_premium_pre_checkout
            await handle_premium_pre_checkout(pre_checkout_query, bot)
            return
        
        # Обработка токенов (старая логика)
        pack_id = payload_data.get("pack_id")
        pack = get_pack_by_id(pack_id)
        
        if not pack:
            await pre_checkout_query.answer(ok=False, error_message="Пакет не найден")
            return
        
        # Проверяем сумму
        if pre_checkout_query.total_amount != int(pack.price_amount):
            await pre_checkout_query.answer(ok=False, error_message="Неверная сумма платежа")
            return
        
        # Подтверждаем платеж
        await pre_checkout_query.answer(ok=True)
    except json.JSONDecodeError:
        await pre_checkout_query.answer(ok=False, error_message="Ошибка в данных платежа")
    except Exception as e:
        logger.error("Ошибка при обработке pre_checkout_query: %s", e, exc_info=True)
        await pre_checkout_query.answer(ok=False, error_message="Внутренняя ошибка")


async def handle_successful_payment(message: Message, bot: Bot) -> None:
    """Обрабатывает успешный платёж в звёздах."""
    payment = message.successful_payment
    if not payment:
        return
    
    try:
        # Извлекаем данные из payload
        payload_data = json.loads(payment.invoice_payload)
        payment_type = payload_data.get("type")
        
        # Обработка премиум подписки
        if payment_type == "premium":
            from premium.handlers import handle_premium_successful_payment
            await handle_premium_successful_payment(message, bot)
            return
        
        # Обработка токенов (старая логика)
        pack_id = payload_data.get("pack_id")
        tokens = payload_data.get("tokens")
        user_id = message.from_user.id
        
        # Проверяем, не был ли этот платёж уже обработан
        payment_id = f"stars_{payment.telegram_payment_charge_id}"
        if was_processed(payment_id):
            logger.info("Платёж %s уже был обработан", payment_id)
            await message.answer("Этот платёж уже был обработан ранее.")
            return
        
        # Начисляем токены
        if tokens:
            add_tokens(user_id, tokens)
            balance = get_token_balance(user_id)
            mark_processed(payment_id, status="paid", tokens=tokens, user_id=user_id)
            
            await message.answer(
                f"✅ <b>Платёж успешно обработан!</b>\n\n"
                f"⭐ Начислено: {tokens} токенов\n"
                f"💰 Текущий баланс: {balance} токенов",
                parse_mode="HTML",
            )
        else:
            logger.warning("Платёж без указания количества токенов: %s", payment_id)
            await message.answer("Платёж получен, но не удалось определить количество токенов.")
    except json.JSONDecodeError:
        logger.error("Ошибка при парсинге payload платежа")
        await message.answer("Ошибка при обработке платежа. Обратитесь в поддержку.")
    except Exception as e:
        logger.error("Ошибка при обработке успешного платежа: %s", e, exc_info=True)
        await message.answer("Ошибка при обработке платежа. Обратитесь в поддержку.")


async def handle_pay_support_command(message: Message) -> None:
    """Обрабатывает команду /paysupport (требуется Telegram для возвратов)."""
    await message.answer(
        "💬 <b>Поддержка по платежам</b>\n\n"
        "По вопросам возврата средств и другим вопросам, связанным с оплатой, "
        "обратитесь к администратору бота.\n\n"
        "Все платежи обрабатываются через Telegram Stars.",
        parse_mode="HTML",
    )


def register_payment_handlers(dp: Dispatcher) -> None:
    dp.message.register(start_topup_via_command, Command("topup"))
    dp.message.register(start_topup_via_button, lambda m: m.text == "💰 Пополнить баланс")
    dp.message.register(handle_pay_support_command, Command("paysupport"))

    dp.callback_query.register(handle_topup_help, lambda c: c.data == PAY_HELP_CALLBACK)
    # Регистрируем обработчик выбора в меню пополнения (должен быть до других обработчиков)
    dp.callback_query.register(
        handle_topup_choice,
        lambda c: c.data is not None and (c.data == "topup:tokens" or c.data == "topup:premium"),
    )
    dp.callback_query.register(
        handle_stars_payment_callback,
        lambda c: c.data and c.data.startswith(STARS_PAY_PREFIX),
    )

    # Обработчики платежей
    dp.pre_checkout_query.register(handle_pre_checkout_query)
    dp.message.register(handle_successful_payment, lambda m: m.successful_payment is not None)

