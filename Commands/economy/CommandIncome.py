from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from asyncio import sleep
from ast import literal_eval

from nextcord import (
    SlashOption,
    Color,
    Role,
    TextChannel,
    ui,
    TextInputStyle,
    Embed,
    utils,
    Guild,
    HTTPException,
    Forbidden,
)
from nextcord.abc import GuildChannel

from utilities import CustomInteraction, CustomCog, PermissionHandler, Iterable
from typings import DB_RESPONSE, EconomyGuildSettings
from enums import Emojis

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class IncomeHandler:
    def __init__(self, bot: Smiffy):
        self.bot: Smiffy = bot

        role_income_data = tuple[int, int, Optional[int], Optional[str]]
        self.income_data: dict[int, dict[int, role_income_data]] = {}

        self.economy_manager: EconomyManager = EconomyManager(bot)

    def add_income_data(self, guild_id: int, income_data: dict[int, tuple]):
        """
        The add_income_data function adds income data to the guild's income_data dictionary.

        :param guild_id: Specify the guild id of the server
        :param income_data: Get the tuple with income data
        :return: None
        """

        data: Optional[dict] = self.income_data.get(guild_id)
        run_new_loop: bool = False

        if data is None:
            run_new_loop = True
            data = {}

        data.update(income_data)
        self.income_data[guild_id] = data

        if run_new_loop:
            self.bot.loop.create_task(self.run_incomes(guild_id))

    async def request_data(self):
        """
        The request_data function is called when the cog is loaded.
        It will request all of the data from the database and store it in a dictionary.
        The dictionary will be used to access data for each guild.

        :return: None
        """

        response: Iterable[Optional[DB_RESPONSE]] = await self.bot.db.execute_fetchall(
            "SELECT guild_id, income_roles FROM economy_settings"
        )
        for row in response:
            self.income_data[row[0]] = literal_eval(row[1])

    async def run_incomes(self, guild_id: int) -> None:
        """
        The run_incomes function is a coroutine that runs in the background of the bot.
        It's purpose is to add income to roles at a specified frequency.
        The function takes one argument, guild_id, which specifies which guild's data should be used.

        :param guild_id: Identify the guild that the income is being added to
        :return: None
        """

        while True:
            await sleep(1)

            data: Optional[dict[int, tuple]] = self.income_data.get(guild_id)

            if data is None:
                break

            for role_id, income_data in data.items():
                frequency: int = income_data[0]

                self.bot.loop.call_later(
                    frequency,
                    self.bot.loop.create_task,
                    self.add_income(guild_id, role_id, income_data),
                )

            self.income_data[guild_id] = {}

    async def add_income(self, guild_id: int, role_id: int, role_income_data: tuple):
        """
        The add_income function is a coroutine that adds income to all members of a role.

        :param guild_id: Get the guild object
        :param role_id: Identify the role that is being added to the income loop
        :param role_income_data: Store the data for each role
        :return: None
        """

        if await self.check_income_role_status(guild_id, role_id):
            income: int = role_income_data[1]
            channel_id: Optional[int] = role_income_data[2]
            channel_message: Optional[str] = role_income_data[3]

            guild: Optional[Guild] = await self.bot.getch_guild(guild_id)
            if not guild:
                return

            role: Optional[Role] = await self.bot.getch_role(guild, role_id)
            if not role:
                return

            if channel_id and channel_message:
                channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

                try:
                    if isinstance(channel, TextChannel):
                        await channel.send(channel_message)
                except (HTTPException, Forbidden):
                    pass

            for member in role.members:
                await self.economy_manager.add_user_money(member, {"money": income})

            data: Optional[dict] = self.income_data.get(guild_id)
            if data is not None:
                data.update({role_id: role_income_data})
                self.income_data[guild_id] = data

    async def run_handler(self) -> None:
        """
        The run_handler function is the main function of this cog. It does the following:
            1) Requests data from the database
            2) Runs through each guild in that data and runs incomes for it

        :return: None
        """

        await self.request_data()

        for guild_id in self.income_data:
            self.bot.loop.create_task(self.run_incomes(guild_id))

    async def check_income_role_status(self, guild_id: int, role_id: int) -> bool:
        """
        The check_income_role_status function is used to check if a role has been set as an income role.
        This function will return True if the given role_id is in the database, and False otherwise.
        This is necessary because while the bot is running, the server administrator can remove role from income roles

        :param guild_id: Get the guild id
        :param role_id: Check if the role_id is in the data dict
        :return: A boolean value
        """

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT income_roles from economy_settings WHERE guild_id = ?", (guild_id,)
        )
        if not response or not response[0]:
            return False

        data: dict[int, tuple] = literal_eval(response[0])

        for role in data:
            if role == role_id:
                return True

        return False

    @classmethod
    def setup(cls, bot: Smiffy) -> IncomeHandler:
        handler = cls(bot)

        bot.loop.create_task(handler.run_handler())

        return handler


class IncomeAddModal(ui.Modal):
    def __init__(
        self,
        handler: IncomeHandler,
        role: Role,
        income: int,
        frequency: int,
        channel: Optional[TextChannel] = None,
    ):
        super().__init__("Treść wiadomości po otrzymaniu przychodu")

        self.handler: IncomeHandler = handler

        self.message_content = ui.TextInput(
            label="Treść wiadomości",
            style=TextInputStyle.paragraph,
            required=True,
            max_length=1000,
            min_length=1,
        )

        self.add_item(self.message_content)

        self.role: Role = role
        self.income: int = income
        self.frequency: int = frequency
        self.channel_id: Optional[int] = None if not channel else channel.id

    async def callback(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        await interaction.response.defer()

        content: Optional[str] = self.message_content.value
        bot: Smiffy = interaction.bot

        data_to_save: tuple[int, int, Optional[int], Optional[str]] = (
            self.frequency,
            self.income,
            self.channel_id,
            content,
        )

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT income_roles FROM economy_settings WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            return

        if response[0]:
            data: dict[int, tuple] = literal_eval(response[0])
            if len(data) >= 25:
                await interaction.send_error_message(
                    description="Osiągnięto limit `25` przypisanych przychodów do roli."
                )
                return

            data[self.role.id] = data_to_save
        else:
            data: dict[int, tuple] = {self.role.id: data_to_save}

        await bot.db.execute_fetchone(
            "UPDATE economy_settings SET income_roles = ? WHERE guild_id = ?",
            (str(data), interaction.guild.id),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} dodano przychód: `{self.income}$`/`{self.frequency}s` "
            f"dla roli: {self.role.mention}",
        )

        self.handler.add_income_data(guild_id=interaction.guild.id, income_data=data)


class CommandIncome(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot)

        self.income_handler: IncomeHandler = IncomeHandler.setup(bot)

    @EconomyCog.main.subcommand(name="przychód")  # pylint: disable=no-member
    async def economy_income(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @economy_income.subcommand(name="dodaj", description="Dodaj przychód dla roli")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def income_add(
        self,
        interaction: CustomInteraction,
        role: Role = SlashOption(name="rola", description="Podaj rolę której chcesz przypisać przychód"),
        income: int = SlashOption(name="przychód_pieniędzy", description="Podaj ilość pieniędzy"),
        frequency: int = SlashOption(
            name="częstotliwość_przychodu",
            description="Podaj częstotliwość przychodu pieniędzy w sekundach",
        ),
        channel: Optional[TextChannel] = SlashOption(
            name="kanał_powiadomień",
            description="Podaj kanał powiadomień o przychodach",
        ),
    ):
        assert interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        guild_settings: EconomyGuildSettings = await manager.get_guild_settings(interaction.guild)

        if role.is_bot_managed() or role.is_default():
            return await interaction.send_error_message(description="Podana rola nie może zostać użyta.")

        if frequency < 60:
            return await interaction.send_error_message(
                description="Częstotliwość przychodu nie może być niższa niż `60s`"
            )
        if income > guild_settings["max_balance"]:
            return await interaction.send_error_message(
                description="Przychód za role nie może być większy od maksymalnego balansu na serwerze."
            )

        modal: IncomeAddModal = IncomeAddModal(self.income_handler, role, income, frequency, channel)

        if channel:
            await interaction.response.send_modal(modal)
        else:
            await modal.callback(interaction)

    @economy_income.subcommand(  # pyright: ignore
        name="usuń", description="Usuwa przychód przypisany do roli"
    )
    @PermissionHandler(manage_guild=True)
    async def income_delete(
        self,
        interaction: CustomInteraction,
        role: Role = SlashOption(name="rola", description="Podaj rolę której chcesz usunać przychód"),
    ):
        assert interaction.guild

        await interaction.response.defer()

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT income_roles FROM economy_settings WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(
                description=f"Nie odnalazłem przypisanego przychodu do roli: {role.mention}"
            )

        if not response[0]:
            return await interaction.send_error_message(
                description=f"Nie odnalazłem przypisanego przychodu do roli: {role.mention}"
            )
        data: dict[int, tuple] = literal_eval(response[0])
        try:
            del data[role.id]
        except KeyError:
            return await interaction.send_error_message(
                description=f"Nie odnalazłem przypisanego przychodu do roli: {role.mention}"
            )

        await self.bot.db.execute_fetchone(
            "UPDATE economy_settings SET income_roles = ? WHERE guild_id = ?",
            (str(data), interaction.guild.id),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie usunięto {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Usunięto przychód dla roli: {role.mention}",
        )

    @economy_income.subcommand(  # pyright: ignore
        name="lista", description="Lista ról z przypisanymi dochodami"
    )
    @PermissionHandler(manage_guild=True)
    async def income_list(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT income_roles FROM economy_settings WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(
                description="Na serwerze nie ma żadnych ról z przypisanymi dochodami."
            )

        if not response[0] or len(response[0]) == 2:
            return await interaction.send_error_message(
                description="Na serwerze nie ma żadnych ról z przypisanymi dochodami."
            )

        income_roles: dict[int, tuple] = literal_eval(response[0])

        embed = Embed(
            title="`📃` Lista ról z przychodami",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        for role_id, data in income_roles.items():
            role: Optional[Role] = await self.bot.getch_role(guild=interaction.guild, role_id=role_id)
            if role:
                interval: int = data[0]
                income: int = data[1]
                channel_id: Optional[int] = data[2]
                channel_mention: str = "`Brak`"

                if channel_id:
                    channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)
                    if isinstance(channel, TextChannel):
                        channel_mention = channel.mention

                embed.add_field(
                    name=f"`📌` Rola: {role}",
                    value=f"- Przychód: `{income}$`/`{interval}s`\n- Kanał powiadomień: {channel_mention}",
                )

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandIncome(bot))
