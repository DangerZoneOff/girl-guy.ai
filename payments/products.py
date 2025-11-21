"""
Каталог пакетов токенов для пополнения.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable, List, Optional

DEFAULT_ASSET = os.getenv("TRIBUTE_DEFAULT_ASSET", "XTR")


@dataclass(frozen=True)
class TokenPack:
    pack_id: str
    title: str
    description: str
    price_amount: float
    tokens: int
    asset: str = DEFAULT_ASSET
    tribute_url: str | None = None
    product_id: int | None = None

    @property
    def price_label(self) -> str:
        return f"{self.price_amount:g} {self.asset}"


TOKEN_PACKS: List[TokenPack] = [
    # Пакеты для оплаты в Telegram Stars (1 звезда = 1 токен)
    TokenPack(
        pack_id="stars_30",
        title="50 токенов",
        description="30 звёзд = 50 токенов",
        price_amount=30,
        tokens=50,
        asset="⭐",
    ),
    TokenPack(
        pack_id="stars_100",
        title="200 токенов",
        description="100 звёзд = 200 токенов",
        price_amount=100,
        tokens=200,
        asset="⭐",
    ),
    TokenPack(
        pack_id="stars_500",
        title="750 токенов",
        description="500 звёзд = 750 токенов",
        price_amount=500,
        tokens=750,
        asset="⭐",
    ),
    TokenPack(
        pack_id="stars_999",
        title="1750 токенов",
        description="999 звёзд = 1750 токенов",
        price_amount=999,
        tokens=1750,
        asset="⭐",
    ),
    # Tribute пакет (временно отключен)
    # TokenPack(
    #     pack_id="premium",
    #     title="Premium подписка",
    #     description="Безлимитное общение и создание персонажей",
    #     price_amount=100,
    #     tokens=9999,
    #     tribute_url="https://t.me/tribute/app?startapp=pnar",
    #     product_id=89059,
    # ),
]


def iter_token_packs() -> Iterable[TokenPack]:
    return list(TOKEN_PACKS)


def get_pack_by_id(pack_id: str | None) -> Optional[TokenPack]:
    if not pack_id:
        return None
    for pack in TOKEN_PACKS:
        if pack.pack_id == pack_id:
            return pack
    return None


__all__ = ["TokenPack", "TOKEN_PACKS", "iter_token_packs", "get_pack_by_id"]


