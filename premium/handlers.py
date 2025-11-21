"""
Обработчики для премиум подписки.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .subscription import (
    is_premium,
    get_premium_status,
    activate_premium,
    get_premium_expiry,
    PREMIUM_PLANS,
)
from payments.stars_orders_store import mark_processed, was_processed

logger = logging.getLogger(__name__)

PREMIUM_PAY_PREFIX = "premium:pay:"
PREMIUM_INFO_CALLBACK = "premium:info"


async def show_premium_menu(message: Message) -> None:
    """Показывает меню премиум подписки с выбором тарифов."""
    user_id = message.from_user.id
    premium_active = is_premium(user_id)
    
    if premium_active:
        expiry = get_premium_expiry(user_id)
        status = get_premium_status(user_id)
        
        if expiry:
            expiry_str = expiry.strftime("%d.%m.%Y")
            plan_type = status.get("plan_type", 1) if status else 1
            plan = PREMIUM_PLANS.get(plan_type, {})
            weeks = plan.get("weeks", 1)
            unlimited = plan.get("unlimited", False)
            
            tokens_text = ""
            if unlimited:
                tokens_text = "♾️ Токены: <b>бесконечные</b>"
            else:
                from SMS.tokens import get_token_balance
                balance = get_token_balance(user_id)
                tokens_text = f"💰 Баланс: {balance} токенов"
            
            text = (
                "⭐ <b>Премиум подписка активна</b>\n\n"
                f"📅 Действует до: {expiry_str}\n"
                f"{tokens_text}\n\n"
                "<b>Преимущества:</b>\n"
                "✨ Неограниченное создание персонажей\n"
                "📝 Удлиненные ответы от ИИ"
            )
        else:
            text = "⭐ <b>Премиум подписка активна</b>"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="ℹ️ Информация", callback_data=PREMIUM_INFO_CALLBACK)
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        # Показываем тарифы
        text = (
            "⭐ <b>Премиум подписка</b>\n\n"
            "Оплата в Telegram Stars.\n"
            "Выбери тариф ниже, оплати звёздами, и подписка автоматически активируется.\n\n"
            "<b>Преимущества всех тарифов:</b>\n"
            "✨ Неограниченное создание персонажей\n"
            "📝 Удлиненные ответы от ИИ"
        )
        
        builder = InlineKeyboardBuilder()
        for plan_id in PREMIUM_PLANS.keys():
            plan = PREMIUM_PLANS[plan_id]
            weeks = plan["weeks"]
            price = plan["price_stars"]
            tokens = plan["tokens"]
            unlimited = plan.get("unlimited", False)
            callback_data = f"{PREMIUM_PAY_PREFIX}{plan_id}"
            
            # Формируем текст кнопки: "⭐ 1 Неделя Premium · 250⭐" или "⭐ 1 Месяц Premium · 999⭐"
            if plan_id == 4:
                period_text = "1 Месяц"
            else:
                period_text = f"{weeks} {'неделя' if weeks == 1 else 'недели' if weeks < 5 else 'недель'}"
            button_text = f"⭐ {period_text} Premium · {price}⭐"
            
            builder.button(
                text=button_text,
                callback_data=callback_data
            )
        # Каждая кнопка на отдельной строке (как в токенах)
        builder.adjust(1)
        builder.button(text="ℹ️ Информация", callback_data=PREMIUM_INFO_CALLBACK)
        
        keyboard = builder.as_markup()
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_premium_command(message: Message) -> None:
    """Обработчик команды /premium."""
    await show_premium_menu(message)


async def handle_premium_info(call: CallbackQuery) -> None:
    """Обработчик кнопки информации о премиум."""
    try:
        await call.answer()
    except Exception:
        pass  # Игнорируем ошибки ответа на callback
    
    if not call.message:
        logger.error("handle_premium_info: call.message is None")
        return
    
    user_id = call.from_user.id
    logger.info(f"handle_premium_info вызван для user_id={user_id}, callback_data={call.data}")
    premium_active = is_premium(user_id)
    
    if premium_active:
        expiry = get_premium_expiry(user_id)
        status = get_premium_status(user_id)
        
        if expiry:
            expiry_str = expiry.strftime("%d.%m.%Y")
            plan_type = status.get("plan_type", 1) if status else 1
            plan = PREMIUM_PLANS.get(plan_type, {})
            weeks = plan.get("weeks", 1)
            unlimited = plan.get("unlimited", False)
            
            tokens_text = ""
            if unlimited:
                tokens_text = "♾️ Токены: <b>бесконечные</b>"
            else:
                from SMS.tokens import get_token_balance
                balance = get_token_balance(user_id)
                tokens_text = f"💰 Баланс: {balance} токенов"
            
            # Формируем текст срока
            if plan_type == 4:
                period_text = "1 месяц"
            else:
                period_text = f"{weeks} {'неделя' if weeks == 1 else 'недели' if weeks < 5 else 'недель'}"
            
            text = (
                "⭐ <b>Ваша премиум подписка</b>\n\n"
                f"📅 Действует до: {expiry_str}\n"
                f"⏱️ Срок: {period_text}\n"
                f"{tokens_text}\n\n"
                "<b>Активные преимущества:</b>\n"
                "✅ Неограниченное создание персонажей\n"
                "✅ Удлиненные ответы от ИИ"
            )
        else:
            text = "⭐ <b>Премиум подписка активна</b>"
    else:
        text = (
            "⭐ <b>О премиум подписке</b>\n\n"
            "<b>Преимущества всех тарифов:</b>\n"
            "✨ Неограниченное создание персонажей\n"
            "📝 Удлиненные ответы от ИИ\n\n"
            "<b>Доступные тарифы:</b>\n"
        )
        
        for plan_id, plan in PREMIUM_PLANS.items():
            weeks = plan["weeks"]
            price = plan["price_stars"]
            tokens = plan["tokens"]
            unlimited = plan.get("unlimited", False)
            
            if unlimited:
                tokens_text = "♾️ Безлимит"
            else:
                tokens_text = f"{tokens} токенов"
            
            # Формируем текст периода
            if plan_id == 4:
                period_text = "1 месяц"
            else:
                period_text = f"{weeks} {'неделя' if weeks == 1 else 'недели' if weeks < 5 else 'недель'}"
            
            discount_text = ""
            if plan_id > 1:
                if plan_id == 4:
                    # Для месяца считаем скидку от 4 недель
                    base_price = PREMIUM_PLANS[1]["price_stars"] * 4
                else:
                    base_price = PREMIUM_PLANS[1]["price_stars"] * weeks
                discount = int((1 - price / base_price) * 100) if base_price > 0 else 0
                if discount > 0:
                    discount_text = f" (скидка {discount}%)"
            
            text += (
                f"\n<b>{plan_id}. {period_text}</b>\n"
                f"   {tokens_text} - {price}⭐{discount_text}"
            )
    
    await call.message.answer(text, parse_mode="HTML")


async def handle_premium_payment_callback(call: CallbackQuery, bot: Bot) -> None:
    """Обрабатывает нажатие на кнопку оплаты премиум подписки."""
    await call.answer()
    
    user_id = call.from_user.id
    
    # Проверяем, не активна ли уже подписка
    if is_premium(user_id):
        await call.message.answer("У тебя уже есть активная премиум подписка!")
        return
    
    # Извлекаем тип тарифа из callback_data
    if not call.data or not call.data.startswith(PREMIUM_PAY_PREFIX):
        await call.message.answer("Ошибка: неверные данные.")
        return
    
    try:
        # PREMIUM_PAY_PREFIX = "premium:pay:", так что после префикса идет plan_id
        plan_id_str = call.data[len(PREMIUM_PAY_PREFIX):]
        plan_id = int(plan_id_str)
    except (ValueError, IndexError):
        logger.error(f"Ошибка парсинга plan_id из callback_data: {call.data}")
        await call.message.answer("Ошибка: неверный тариф.")
        return
    
    if plan_id not in PREMIUM_PLANS:
        await call.message.answer("Ошибка: тариф не найден.")
        return
    
    plan = PREMIUM_PLANS[plan_id]
    weeks = plan["weeks"]
    price = plan["price_stars"]
    tokens = plan["tokens"]
    unlimited = plan.get("unlimited", False)
    
    # Формируем описание для invoice
    if unlimited:
        tokens_desc = "♾️ Безлимитные токены"
    else:
        tokens_desc = f"💰 {tokens} токенов на баланс"
    
    description = (
        f"{tokens_desc}\n"
        "✨ Неограниченное создание персонажей\n"
        "📝 Удлиненные ответы от ИИ"
    )
    
    try:
        # Создаём payload
        payload_data = {
            "type": "premium",
            "user_id": user_id,
            "plan_type": plan_id,
            "weeks": weeks,
        }
        payload = json.dumps(payload_data)
        
        # Создаём кнопку оплаты
        builder = InlineKeyboardBuilder()
        builder.button(text=f"Оплатить {price} ⭐", pay=True)
        
        # Формируем текст периода для invoice
        if plan_id == 4:
            period_text = "1 месяц"
            period_label = "1 мес"
        else:
            period_text = f"{weeks} {'неделя' if weeks == 1 else 'недели' if weeks < 5 else 'недель'}"
            period_label = f"{weeks} {'нед' if weeks == 1 else 'нед'}"
        
        # Отправляем счёт на оплату
        await bot.send_invoice(
            chat_id=user_id,
            title=f"⭐ Премиум подписка ({period_text})",
            description=description,
            payload=payload,
            provider_token="",  # Для Telegram Stars должен быть пустой
            currency="XTR",  # XTR - валюта Telegram Stars
            prices=[LabeledPrice(label=f"Премиум {period_label}", amount=price)],
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error("Ошибка при создании платежа премиум: %s", e, exc_info=True)
        await call.message.answer(
            "Не удалось создать платёж. Попробуй позже или обратись в поддержку."
        )


async def handle_premium_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
    """Обрабатывает предчекаут-запрос для премиум подписки."""
    try:
        # Проверяем payload
        payload_data = json.loads(pre_checkout_query.invoice_payload)
        payment_type = payload_data.get("type")
        
        if payment_type != "premium":
            await pre_checkout_query.answer(ok=False, error_message="Неверный тип платежа")
            return
        
        plan_type = payload_data.get("plan_type")
        if plan_type not in PREMIUM_PLANS:
            await pre_checkout_query.answer(ok=False, error_message="Неверный тариф")
            return
        
        plan = PREMIUM_PLANS[plan_type]
        expected_price = plan["price_stars"]
        
        # Проверяем сумму
        if pre_checkout_query.total_amount != expected_price:
            await pre_checkout_query.answer(ok=False, error_message="Неверная сумма платежа")
            return
        
        # Подтверждаем платеж
        await pre_checkout_query.answer(ok=True)
    except json.JSONDecodeError:
        await pre_checkout_query.answer(ok=False, error_message="Ошибка в данных платежа")
    except Exception as e:
        logger.error("Ошибка при обработке pre_checkout_query премиум: %s", e, exc_info=True)
        await pre_checkout_query.answer(ok=False, error_message="Внутренняя ошибка")


async def handle_premium_successful_payment(message: Message, bot: Bot) -> None:
    """Обрабатывает успешный платёж премиум подписки."""
    payment = message.successful_payment
    if not payment:
        return
    
    try:
        # Извлекаем данные из payload
        payload_data = json.loads(payment.invoice_payload)
        payment_type = payload_data.get("type")
        user_id = message.from_user.id
        
        if payment_type != "premium":
            logger.warning(f"Неверный тип платежа в премиум обработчике: {payment_type}")
            return
        
        # Проверяем, не был ли этот платёж уже обработан
        payment_id = f"premium_{payment.telegram_payment_charge_id}"
        if was_processed(payment_id):
            logger.info("Платёж премиум %s уже был обработан", payment_id)
            await message.answer("Этот платёж уже был обработан ранее.")
            return
        
        # Активируем премиум подписку
        plan_type = payload_data.get("plan_type", 1)
        if plan_type not in PREMIUM_PLANS:
            logger.error(f"Неверный plan_type в платеже: {plan_type}")
            await message.answer("Ошибка: неверный тариф. Обратись в поддержку.")
            return
        
        if activate_premium(user_id, plan_type):
            expiry = get_premium_expiry(user_id)
            expiry_str = expiry.strftime("%d.%m.%Y") if expiry else "неизвестно"
            
            plan = PREMIUM_PLANS[plan_type]
            weeks = plan["weeks"]
            tokens = plan["tokens"]
            unlimited = plan.get("unlimited", False)
            
            # Формируем текст периода
            if plan_type == 4:
                period_text = "1 месяц"
            else:
                period_text = f"{weeks} {'неделя' if weeks == 1 else 'недели' if weeks < 5 else 'недель'}"
            
            tokens_text = "♾️ Безлимитные токены" if unlimited else f"💰 {tokens} токенов на балансе"
            
            mark_processed(payment_id, status="paid", tokens=None, user_id=user_id)
            
            await message.answer(
                f"✅ <b>Премиум подписка активирована!</b>\n\n"
                f"📅 Действует до: {expiry_str}\n"
                f"⏱️ Срок: {period_text}\n"
                f"{tokens_text}\n\n"
                "<b>Теперь доступно:</b>\n"
                "✨ Неограниченное создание персонажей\n"
                "📝 Удлиненные ответы от ИИ",
                parse_mode="HTML",
            )
        else:
            logger.error(f"Не удалось активировать премиум для user_id={user_id}")
            await message.answer("Произошла ошибка при активации подписки. Обратись в поддержку.")
            
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга payload премиум платежа: {e}")
        await message.answer("Ошибка при обработке платежа. Обратись в поддержку.")
    except Exception as e:
        logger.error(f"Ошибка при обработке премиум платежа: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке платежа. Обратись в поддержку.")


def register_premium_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики премиум подписки."""
    # Команда /premium
    dp.message.register(handle_premium_command, Command("premium"))
    
    # Callback кнопки - сначала регистрируем обработчик информации (более специфичный)
    dp.callback_query.register(
        handle_premium_info,
        lambda c: c.data == PREMIUM_INFO_CALLBACK
    )
    # Затем обработчик платежей (менее специфичный, но с префиксом)
    dp.callback_query.register(
        handle_premium_payment_callback,
        lambda c: c.data and c.data.startswith(PREMIUM_PAY_PREFIX)
    )
    
    # Pre-checkout и successful payment обрабатываются в payments/handlers.py
    # с проверкой типа платежа в payload

