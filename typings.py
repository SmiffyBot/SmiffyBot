# pylint: disable=unused-import
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, TypedDict, TypeVar, Union

from aiosqlite import Row

from utilities import Logger

if TYPE_CHECKING:
    from nextcord import Interaction, Member, User, VoiceProtocol


DB_RESPONSE = Row
Bot_Settings = Any
BotLogger = Logger

RED_COLOR: tuple[int, ...] = (252, 45, 55)

PlayerT = TypeVar("PlayerT", bound="VoiceProtocol")
InterT = TypeVar("InterT", bound="Interaction")
UserType = Union["Member", "User"]


class EconomyUserData(TypedDict):
    guild_id: int
    user_id: int
    money: int
    bank_money: int
    items: list[str]


class EconomyGuildSettings(TypedDict):
    guild_id: int
    start_balance: int
    max_balance: int
    work_win_rate: int
    work_cooldown: int
    work_min_income: int
    work_max_income: int
    coin_flip_cooldown: int
    income_roles: dict


class EconomyItemData(TypedDict):
    guild_id: int
    name: str
    description: str
    price: int
    reply_message: Optional[str]
    required_role: Optional[int]
    given_role: Optional[int]
    item_id: str


class UserlevelingData(TypedDict):
    name: str
    avatar_url: str
    level: int
    xp: int
    next_level_xp: int
    percentage: int
    rank: int
