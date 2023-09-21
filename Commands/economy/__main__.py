from __future__ import annotations

from ast import literal_eval
from asyncio import sleep
from datetime import datetime
from random import randint
from typing import TYPE_CHECKING, Iterable

from cooldowns import (
    Cooldown,
    SlashBucket,
    define_shared_cooldown,
    get_shared_cooldown,
    reset_bucket,
)
from nextcord import slash_command

from typings import EconomyGuildSettings, EconomyItemData, EconomyUserData
from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from nextcord import Guild, Member

    from bot import Smiffy
    from utilities import DB_RESPONSE, Optional


class EconomyManager:
    def __init__(self, bot: Smiffy):
        self.bot: Smiffy = bot

    @staticmethod
    def get_waited_seconds(inter: CustomInteraction, cooldown_id: str) -> Optional[int]:
        cooldown: Cooldown = get_shared_cooldown(cooldown_id)

        try:
            cooldown_end: Optional[datetime] = cooldown.get_cooldown_times_per(
                bucket=cooldown.get_bucket(inter)  # pyright: ignore
            ).next_reset  # pyright: ignore

            if not cooldown_end:
                raise AttributeError

        except AttributeError:
            return None

        cooldown_seconds: int = (cooldown_end - datetime.utcnow()).seconds
        waited_seconds: int = 43200 - cooldown_seconds
        return waited_seconds

    async def check_cooldown(
        self,
        cog: CustomCog,
        interaction: CustomInteraction,
        **kwargs,  # pylint: disable=unused-argument
    ) -> bool:
        assert interaction.guild

        if not interaction.application_command:
            return False

        cooldown_id: str = "command_work"
        db_label: str = "work_cooldown"

        if interaction.application_command.name == "rzut_moneta":
            cooldown_id = "command_coinflip"
            db_label = "coin_flip_cooldown"

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            f"SELECT {db_label} FROM economy_settings WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response or not response[0]:
            return True

        cooldown: Cooldown = get_shared_cooldown(cooldown_id)
        waited_seconds: Optional[int] = self.get_waited_seconds(interaction, cooldown_id)
        if not waited_seconds:
            return True

        if waited_seconds >= response[0]:
            reset_bucket(cooldown.func, interaction)  # pyright: ignore
            return False

        return True

    def define_cooldowns(self):
        define_shared_cooldown(
            1,
            43200,
            bucket=SlashBucket.author,
            cooldown_id="command_work",
            check=self.check_cooldown,
        )

        define_shared_cooldown(
            1,
            43200,
            bucket=SlashBucket.author,
            cooldown_id="command_coinflip",
            check=self.check_cooldown,
        )

    async def delete_guild_item(self, guild: Guild, item_name: str) -> None:
        await self.bot.db.execute_fetchone(
            "DELETE FROM economy_shop WHERE guild_id = ? AND name = ?",
            (guild.id, item_name),
        )

    async def edit_guild_item(
        self,
        guild: Guild,
        item_name: str,
        data: dict,
    ) -> None:
        item_data: Optional[EconomyItemData] = await self.get_guild_item(guild, item_name=item_name)

        if not item_data:
            return None

        item_data.update(data)  # pyright: ignore

        sql: str = "UPDATE economy_shop SET {} = ? WHERE guild_id = ? AND name = ?"
        sql = sql.format(" = ?, ".join(x for x in item_data if x != "guild_id"))
        values = tuple(item_data.values())[1:] + (
            guild.id,
            item_name,
        )

        await self.bot.db.execute_fetchone(sql, values)

    async def generate_item_id(self, guild: Guild) -> str:
        item_id: str = f"sf-{randint(10000, 99999)}{str(guild.id)[0:3]}"

        while await self.get_guild_item(guild, item_id=item_id):
            item_id: str = f"sf-{randint(10000, 99999)}{str(guild.id)[0:3]}"
            await sleep(0.1)

        return item_id

    async def create_guild_item(self, item_data: EconomyItemData) -> None:
        await self.bot.db.execute_fetchone(
            f"INSERT INTO economy_shop({', '.join(item_data.keys())}) VALUES(?,?,?,?,?,?,?,?)",
            tuple(item_data.values()),
        )

    async def get_guild_shop(self, guild: Guild) -> list[EconomyItemData]:
        response: Optional[Iterable[DB_RESPONSE]] = await self.bot.db.execute_fetchall(
            "SELECT * FROM economy_shop WHERE guild_id = ?",
            (guild.id,),
        )
        items: list[EconomyItemData] = []

        for item_data in response:
            items.append(
                EconomyItemData(
                    guild_id=guild.id,
                    name=item_data[1],
                    description=item_data[2],
                    price=item_data[3],
                    reply_message=item_data[4],
                    required_role=item_data[5],
                    given_role=item_data[6],
                    item_id=item_data[7],
                )
            )

        return items

    async def get_guild_item(
        self,
        guild: Guild,
        item_name: Optional[str] = None,
        item_id: Optional[str] = None,
    ) -> Optional[EconomyItemData]:
        if not item_id and not item_name:
            return None

        if item_name:
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM economy_shop WHERE guild_id = ? AND name = ?",
                (guild.id, item_name),
            )
        else:
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM economy_shop WHERE guild_id = ? AND item_id = ?",
                (guild.id, item_id),
            )

        if not response:
            return None

        return EconomyItemData(
            guild_id=guild.id,
            name=response[1],
            description=response[2],
            price=response[3],
            reply_message=response[4],
            required_role=response[5],
            given_role=response[6],
            item_id=response[7],
        )

    async def remove_user_money(self, user: Member, amount: int) -> EconomyUserData:
        (
            money,
            bank_money,
        ) = await self.get_user_balance(user)
        money -= amount

        return await self.update_user_account(
            user=user,
            data={
                "money": money,
                "bank_money": bank_money,
            },
        )

    async def add_user_money(
        self,
        user: Member,
        money_data: dict[str, int],
    ) -> EconomyUserData:
        (
            money,
            bank_money,
        ) = await self.get_user_balance(user)
        guild_settings: EconomyGuildSettings = await self.get_guild_settings(guild=user.guild)

        money_to_add: int = money_data.get("money", 0)
        bank_money_to_add: int = money_data.get("bank_money", 0)
        max_balance: int = guild_settings["max_balance"]

        if (money + bank_money) + (money_to_add + bank_money_to_add) >= max_balance:
            money: int = max_balance - bank_money
        else:
            money += money_to_add
            bank_money += bank_money_to_add

        return await self.update_user_account(
            user=user,
            data={
                "money": money,
                "bank_money": bank_money,
            },
        )

    async def get_all_guild_accounts(self, guild: Guild) -> list[EconomyUserData]:
        accounts_data: list[EconomyUserData] = []

        response: Optional[Iterable[DB_RESPONSE]] = await self.bot.db.execute_fetchall(
            "SELECT * FROM economy_users WHERE guild_id = ?",
            (guild.id,),
        )
        if not response:
            return accounts_data

        for account_data in response:
            accounts_data.append(
                EconomyUserData(
                    guild_id=guild.id,
                    user_id=account_data[1],
                    money=account_data[2],
                    bank_money=account_data[3],
                    items=literal_eval(account_data[4]),
                )
            )
        return accounts_data

    async def update_user_account(
        self,
        user: Member,
        data: dict[str, int | list],
    ) -> EconomyUserData:
        user_data: EconomyUserData = await self.get_user_data(user)
        user_data.update(data)  # pyright: ignore

        await self.bot.db.execute_fetchone(
            "UPDATE economy_users SET money = ?, bank_money = ?, items = ? WHERE guild_id = ? AND user_id = ?",
            (
                user_data["money"],
                user_data["bank_money"],
                str(user_data["items"]),
                user.guild.id,
                user.id,
            ),
        )

        return user_data

    async def get_user_balance(self, user: Member) -> tuple[int, int]:
        user_data: EconomyUserData = await self.get_user_data(user)
        return (
            user_data["money"],
            user_data["bank_money"],
        )

    async def get_user_data(self, user: Member) -> EconomyUserData:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM economy_users WHERE guild_id = ? AND user_id = ?",
            (user.guild.id, user.id),
        )
        if not response:
            user_data: EconomyUserData = await self.create_user_account(user)
            return user_data

        user_data: EconomyUserData = EconomyUserData(
            guild_id=user.guild.id,
            user_id=user.id,
            money=response[2],
            bank_money=response[3],
            items=literal_eval(response[4]),
        )

        return user_data

    async def create_user_account(self, user: Member) -> EconomyUserData:
        guild_settings: EconomyGuildSettings = await self.get_guild_settings(user.guild)
        start_balance: int = guild_settings["start_balance"]

        await self.bot.db.execute_fetchone(
            "INSERT INTO economy_users(guild_id, user_id, money, bank_money, items) VALUES(?,?,?,?,?)",
            (
                user.guild.id,
                user.id,
                start_balance,
                0,
                "[]",
            ),
        )

        user_data: EconomyUserData = EconomyUserData(
            guild_id=user.guild.id,
            user_id=user.id,
            money=start_balance,
            bank_money=0,
            items=[],
        )

        return user_data

    async def delete_user_account(self, guild: Guild, user_id: int) -> None:
        await self.bot.db.execute_fetchone(
            "DELETE FROM economy_users WHERE guild_id = ? AND user_id = ?",
            (guild.id, user_id),
        )

    async def set_guild_economy_status(self, guild: Guild, status: bool) -> None:
        if status:
            await self.setup_guild_settings(guild)
        else:
            await self.bot.db.execute_fetchone(
                "DELETE FROM economy_settings WHERE guild_id = ?",
                (guild.id,),
            )

    async def get_guild_economy_status(self, guild: Guild) -> bool:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM economy_settings WHERE guild_id = ?",
            (guild.id,),
        )
        if not response:
            return False

        return True

    async def update_guild_settings(self, guild: Guild, data: dict) -> None:
        guild_settings: EconomyGuildSettings = await self.get_guild_settings(guild)
        guild_settings.update(data)  # pyright: ignore

        values: tuple = tuple(
            (
                str(value) if key == "income_roles" else value
                for key, value in guild_settings.items()
                if key != "guild_id"
            )
        ) + (guild.id,)

        await self.bot.db.execute_fetchone(
            "UPDATE economy_settings SET start_balance = ?, max_balance = ?, work_win_rate = ?, "
            "work_cooldown = ?, work_min_income = ?, work_max_income = ?, coin_flip_cooldown = ?, income_roles = ? "
            "WHERE guild_id = ?",
            values,
        )

    async def get_guild_settings(self, guild: Guild) -> EconomyGuildSettings:
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM economy_settings WHERE guild_id = ?",
            (guild.id,),
        )
        if not response:
            guild_settings: EconomyGuildSettings = await self.setup_guild_settings(guild)
            return guild_settings

        return EconomyGuildSettings(
            guild_id=guild.id,
            start_balance=response[1],
            max_balance=response[2],
            work_win_rate=response[3],
            work_cooldown=response[4],
            work_min_income=response[5],
            work_max_income=response[6],
            coin_flip_cooldown=response[7],
            income_roles=literal_eval(response[8]),
        )

    async def setup_guild_settings(self, guild: Guild) -> EconomyGuildSettings:
        await self.bot.db.execute_fetchone(
            "INSERT INTO economy_settings(guild_id, start_balance, max_balance, work_win_rate, "
            "work_cooldown, work_min_income, work_max_income, coin_flip_cooldown, income_roles) "
            "VALUES(?,?,?,?,?,?,?,?, ?)",
            (
                guild.id,
                100,
                100000000,
                70,
                300,
                50,
                200,
                30,
                "{}",
            ),
        )
        return EconomyGuildSettings(
            guild_id=guild.id,
            start_balance=100,
            max_balance=100000000,
            work_win_rate=70,
            work_cooldown=300,
            work_min_income=50,
            work_max_income=200,
            coin_flip_cooldown=30,
            income_roles={},
        )


class EconomyCog(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot)

        EconomyManager(bot).define_cooldowns()

    @slash_command(name="ekonomia", dm_permission=False)
    async def main(self, inter: CustomInteraction):  # pylint: disable=unused-argument
        ...


def setup(bot: Smiffy):
    bot.add_cog(EconomyCog(bot))
