from __future__ import annotations

from ast import literal_eval
from asyncio import exceptions, sleep
from datetime import timedelta
from random import randint
from time import time
from typing import TYPE_CHECKING, Optional

from humanfriendly import parse_timespan
from nextcord import (
    ButtonStyle,
    Color,
    Embed,
    Member,
    Message,
    SelectOption,
    SlashOption,
    TextChannel,
    Thread,
)
from nextcord import errors as nextcord_errors
from nextcord import slash_command, ui, utils
from nextcord.ext.commands import errors

from converters import MemberConverter
from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class WarnsList(ui.Select):
    def __init__(self, warnings_data: dict[str, str]):
        self.warnings_data: dict[str, str] = warnings_data

        amount_of_warns: int = len(warnings_data)
        pages: int = round((amount_of_warns / 5) + 0.5)
        pages_list: list[SelectOption] = []

        for page in range(1, pages + 1):
            pages_list.append(
                SelectOption(
                    label=f"Strona: {page}",
                    description=f"Wyświetla ostrzeżenia na stronie {page}",
                    value=str(page),
                    emoji="📖",
                )
            )

        super().__init__(
            placeholder="Wybierz następną stronę ostrzeżeń",
            options=pages_list,
        )

    async def callback(self, interaction: CustomInteraction) -> None:
        if not interaction.message:
            await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")
            return

        selected_page: int = int(self.values[0]) - 1
        min_range: int = selected_page * 5
        max_range: int = (selected_page * 5) + 5

        embed: Embed = interaction.message.embeds[0]
        embed.clear_fields()

        for index, warn_id in enumerate(self.warnings_data):
            if index >= min_range:
                embed.add_field(
                    name=f"`📕` {index + 1}. Powód: {self.warnings_data[warn_id]}",
                    value=f"{Emojis.REPLY.value} ID: `{warn_id}`",
                    inline=False,
                )

            if index + 1 == max_range:
                break

        await interaction.message.edit(embed=embed)


class WarnsListView(ui.View):
    def __init__(self, warnings_data: dict[str, str]):
        super().__init__(timeout=None)

        self.add_item(WarnsList(warnings_data))


class DeleteAllWarnsView(ui.View):
    def __init__(
        self,
        author_id: int,
        bot: Smiffy,
        person: Optional[Member] = None,
    ):
        super().__init__(timeout=None)

        self.author_id: int = author_id
        self.bot: Smiffy = bot
        self.person: Optional[Member] = person

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        label="Tak",
        style=ButtonStyle.green,
        emoji="<:suggestionlike:997650032683667506>",
    )
    async def confirm(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        assert interaction.guild and interaction.message

        await interaction.response.defer()

        embed = Embed(
            title="<a:loading:919653287383404586> Usuwanie wszystkich ostrzeżeń...",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        await interaction.edit_original_message(embed=embed, view=None)

        # if not person then it's global, for whole server.
        if not self.person:
            await self.bot.db.execute_fetchone(
                "DELETE FROM warnings WHERE guild_id = ?",
                (interaction.guild.id,),
            )

            embed = Embed(
                title=f"Pomyślnie usunięto {Emojis.GREENBUTTON.value}",
                color=Color.green(),
                description=f"{Emojis.REPLY.value} Pomyślnie usunięto wszystkie ostrzeżenia na serwerze.",
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__}",
                icon_url=self.bot.avatar_url,
            )

            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
            )

        else:
            await self.bot.db.execute_fetchone(
                "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
                (
                    interaction.guild.id,
                    self.person.id,
                ),
            )

            embed = Embed(
                title=f"Pomyślnie usunięto {Emojis.GREENBUTTON.value}",
                color=Color.green(),
                description=f"{Emojis.REPLY.value} Pomyślnie usunięto wszystkie ostrzeżenia: {self.person.mention}",
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__}",
                icon_url=self.bot.avatar_url,
            )

            if interaction.message:
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    embed=embed,
                )

    @ui.button(  # pyright: ignore[reportGeneralTypeIssues]
        label="Nie",
        style=ButtonStyle.red,
        emoji="<:suggestiondislike:997650135209222344>",
    )
    async def cancel(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        if interaction.message:
            await interaction.message.delete()

    async def interaction_check(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        if interaction.user.id == self.author_id:
            return True

        return await interaction.send_error_message(
            description="Nie możesz tego użyć",
            ephemeral=True,
        )


class DeletePunishmentMessage(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        if interaction.user.guild_permissions.manage_messages:
            return True  # Checking if the user who pressed the button has permission manage_messages

        return await interaction.send_error_message(
            description="Nie posiadasz permisji: `Manage_Messages`, aby tego użyć.",
            ephemeral=True,
        )

    @ui.button(
        label="Usuń Wiadomość",
        style=ButtonStyle.gray,
        emoji="❌",
    )  # pyright: ignore[reportGeneralTypeIssues]
    async def delete(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        await interaction.delete_original_message(delay=1)


class CommandWarn(CustomCog):
    @slash_command(
        name="ostrzeżenia",
        description="System ostrzeżeń",
        dm_permission=False,
    )
    async def warnings_system(self, interaction: CustomInteraction):
        pass

    @warnings_system.subcommand(
        name="nadaj",
        description="Nadaje ostrzeżenie osobie.",
    )  # pyright: ignore
    @PermissionHandler(
        moderate_members=True,
        user_role_has_permission="warn",
    )
    async def warn_add(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj osobę którą chcesz zwarnować.",
        ),
        reason: str = SlashOption(
            name="powod",
            description="Podaj powód warna.",
            max_length=256,
        ),
    ):
        assert interaction.guild and isinstance(interaction.user, Member)

        await interaction.response.defer()

        if interaction.user.top_role <= member.top_role or member.id == interaction.guild.owner_id:
            if interaction.guild.owner_id != interaction.user.id:
                return await interaction.send_error_message(
                    description=f"Posiadasz zbyt małe uprawnienia, aby nadać ostrzeżenie osobie: {member.mention}.",
                )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings WHERE guild_id = ? and user_id = ?",
            (interaction.guild.id, member.id),
        )

        if response:
            member_warns: dict = literal_eval(str(response[2]))

            if len(member_warns) >= 50:
                return await interaction.send_error_message(
                    f"Osoba {member.mention} osiągnęła limit `50` ostrzeżeń.",
                )

            new_warn_id: str = f"sf-{randint(10000, 99999)}{str(member.id)[0:3]}"

            while new_warn_id in member_warns.keys():
                new_warn_id: str = f"sf-{randint(10000, 99999)}{str(member.id)[0:3]}"

            member_warns[new_warn_id] = reason

            await self.bot.db.execute_fetchone(
                "UPDATE warnings SET warns = ? WHERE guild_id = ? and user_id = ?",
                (
                    str(member_warns),
                    interaction.guild.id,
                    member.id,
                ),
            )

        else:
            new_warn: dict = {f"sf-{randint(10000, 99999)}{str(member.id)[0:3]}": f"{reason}"}
            member_warns: dict = new_warn

            await self.bot.db.execute_fetchone(
                "INSERT INTO warnings(guild_id, user_id, warns) VALUES(?,?,?)",
                (
                    interaction.guild.id,
                    member.id,
                    str(new_warn),
                ),
            )

        embed = Embed(
            title=f"Pomyślnie nadano ostrzeżenie {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )

        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        embed.add_field(
            name="`👤` Użytkownik",
            value=f"{Emojis.REPLY.value} {member.mention}",
        )

        embed.add_field(
            name="`🗨️` Powód",
            value=f"{Emojis.REPLY.value} `{reason}`",
            inline=False,
        )

        embed.add_field(
            name="`📃` Aktualne ostrzeżenia",
            value=f"{Emojis.REPLY.value} `{len(member_warns)}`",
        )

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        await interaction.send(embed=embed)

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings_punishments WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if response:
            if (
                interaction.guild.me.top_role.position <= member.top_role.position
                or member.id == interaction.guild.owner_id
            ):
                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Nie posiadam wystarczających permisji, "
                    f"aby nadać karę użytkownikowi: {member}",
                )
                embed.set_author(
                    name=interaction.user,
                    icon_url=interaction.user_avatar_url,
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)
                if isinstance(
                    interaction.channel,
                    (TextChannel, Thread),
                ):
                    await interaction.channel.send(embed=embed)
                return

            embed = Embed(
                title=f"Pomyślnie nadano karę {Emojis.GREENBUTTON.value}",
                color=Color.dark_theme(),
                description=f"{Emojis.REPLY.value} {member.mention} otrzymał/a karę za `{len(member_warns)}` ostrzeżeń",
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)

            button_delete_message: ui.View = DeletePunishmentMessage()
            warnings_data: dict[str, tuple[str, str]] = literal_eval(response[1])

            for (
                warn_count,
                punishment_data,
            ) in warnings_data.items():
                if int(warn_count) == len(member_warns):
                    action: str = punishment_data[0]
                    punishment_duration: str = punishment_data[1]

                    embed_description: str = (
                        "{mention} Otrzymał karę: `{punishment}` za **{warn_count}** "
                        "ostrzeżenia na czas: `{duration}`"
                    )

                    if "mute" in action.lower() or "tempban" in action.lower():
                        duration: float = parse_timespan(punishment_duration)

                        if action == "mute":
                            if await self.mute_person(
                                interaction,
                                member,
                                duration,
                            ):
                                embed.description = embed_description.format(
                                    mention=member.mention,
                                    punishment=action.capitalize(),
                                    warn_count=warn_count,
                                    duration=punishment_duration,
                                )

                                if isinstance(
                                    interaction.channel,
                                    (
                                        TextChannel,
                                        Thread,
                                    ),
                                ):
                                    return await interaction.channel.send(
                                        embed=embed,
                                        view=button_delete_message,
                                    )

                        if action == "tempban":
                            if await self.tempban_person(
                                interaction,
                                member,
                                duration,
                            ):
                                embed.description = embed_description.format(
                                    mention=member.mention,
                                    punishment=action.capitalize(),
                                    warn_count=warn_count,
                                    duration=punishment_duration,
                                )

                                if isinstance(
                                    interaction.channel,
                                    (
                                        TextChannel,
                                        Thread,
                                    ),
                                ):
                                    return await interaction.channel.send(
                                        embed=embed,
                                        view=button_delete_message,
                                    )

                        break

                    if action.lower() == "kick":
                        if await self.kick_person(interaction, member):
                            embed.description = embed_description.format(
                                mention=member.mention,
                                punishment=action.capitalize(),
                                warn_count=warn_count,
                                duration=punishment_duration,
                            )
                            if isinstance(
                                interaction.channel,
                                (
                                    TextChannel,
                                    Thread,
                                ),
                            ):
                                return await interaction.channel.send(
                                    embed=embed,
                                    view=button_delete_message,
                                )

                    if action.lower() == "ban":
                        if await self.ban_person(interaction, member):
                            embed.description = embed_description.format(
                                mention=member.mention,
                                punishment=action.capitalize(),
                                warn_count=warn_count,
                                duration=punishment_duration,
                            )
                            if isinstance(
                                interaction.channel,
                                (
                                    TextChannel,
                                    Thread,
                                ),
                            ):
                                return await interaction.channel.send(
                                    embed=embed,
                                    view=button_delete_message,
                                )

    @staticmethod
    async def mute_person(
        interaction: CustomInteraction,
        member: Member,
        duration: float,
    ) -> bool:
        try:
            await member.edit(timeout=timedelta(seconds=duration))
        except nextcord_errors.Forbidden:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"Nie posiadam wystarczających permisji, aby nadać karę użytkownikowi: `{member}`",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)
            return False

        except nextcord_errors.HTTPException:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description="Wystąpił niespodziewany błąd.",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)
            return False

        return True

    async def tempban_person(
        self,
        interaction: CustomInteraction,
        member: Member,
        duration: float,
    ) -> bool:
        assert interaction.guild

        try:
            await member.ban(
                reason="KaryWarny - Smiffy",
                delete_message_days=0,
            )

            ban_duration: int = int(time() + duration) + 7200

            await self.bot.db.execute_fetchone(
                "INSERT INTO tempbans(guild_id, user_id, ban_duration) VALUES(?,?,?)",
                (
                    interaction.guild.id,
                    member.id,
                    ban_duration,
                ),
            )

            async def unban_person():
                assert interaction.guild

                await sleep(duration)
                await interaction.guild.unban(member)

                await self.bot.db.execute_fetchone(
                    "DELETE FROM tempbans WHERE guild_id = ? AND user_id = ?",
                    (
                        interaction.guild.id,
                        member.id,
                    ),
                )

            await self.bot.loop.create_task(unban_person())

        except nextcord_errors.Forbidden:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"Nie posiadam wystarczających permisji, aby nadać karę użytkownikowi: `{member}`",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)
            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"Wystąpił nieoczekiwany błąd: {e}",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)

            return False

        return True

    @staticmethod
    async def kick_person(
        interaction: CustomInteraction,
        member: Member,
    ) -> bool:
        try:
            await member.kick(reason="KaryWarny - Smiffy")
        except nextcord_errors.Forbidden:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"Nie posiadam wystarczających permisji, aby nadać karę użytkownikowi: `{member}`",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)
            return False

        except nextcord_errors.HTTPException:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description="Wystąpił niespodziewany błąd.",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)

            return False

        return True

    @staticmethod
    async def ban_person(
        interaction: CustomInteraction,
        member: Member,
    ) -> bool:
        try:
            await member.ban(reason="KaryWarny - Smiffy")
        except nextcord_errors.Forbidden:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description=f"Nie posiadam wystarczających permisji, aby nadać karę użytkownikowi: `{member}`",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)

            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)
            return False

        except nextcord_errors.HTTPException:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                color=Color.red(),
                timestamp=utils.utcnow(),
                description="Wystąpił niespodziewany błąd.",
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)

            if isinstance(
                interaction.channel,
                (TextChannel, Thread),
            ):
                await interaction.channel.send(embed=embed)

            return False

        return True

    @warnings_system.subcommand(
        name="usuń",
        description="Usuwa ostrzeżenie osobie.",
    )  # pyright: ignore
    @PermissionHandler(
        moderate_members=True,
        user_role_has_permission="warn",
    )
    async def warn_remove(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj osobę której chcesz usunąć ostrzeżenie.",
        ),
        warn_id: str = SlashOption(
            name="warn_id",
            description="Wpisz id warna którego chcesz usunąć. "
            "ID Warna możesz sprawdzić poleceniem: /warnings "
            "<@osoba>",
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings WHERE guild_id = ? and user_id = ?",
            (interaction.guild.id, member.id),
        )

        if not response:
            return await interaction.send_error_message(
                description="Niestety, ale podana osoba nie posiada żadnych ostrzeżeń.",
            )

        warnings_data: dict[str, str] = literal_eval(response[2])

        try:
            warn_reason: str = warnings_data[warn_id]
            del warnings_data[warn_id]
        except KeyError:
            return await interaction.send_error_message(
                "Nieprawidłowe ID Warna. Sprawdzić je możesz, wpisując polecenie: `/ostrzezenia lista`",
            )

        await self.bot.db.execute_fetchone(
            "UPDATE warnings SET warns = ? WHERE guild_id = ? and user_id = ?",
            (
                str(warnings_data),
                interaction.guild.id,
                member.id,
            ),
        )

        embed = Embed(
            title=f"Pomyślnie usunięto ostrzeżenie {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.add_field(
            name="`👤` Użytkownik",
            value=f"{Emojis.REPLY.value} {member.mention}",
        )

        embed.add_field(
            name="`🗨️` Warn",
            value=f"{Emojis.REPLY.value} `{warn_reason}` | **(`{warn_id}`)**",
            inline=False,
        )

        embed.add_field(
            name="`📃` Aktualne ostrzeżenia",
            value=f"{Emojis.REPLY.value} `{len(warnings_data)}`",
        )

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )
        await interaction.send(embed=embed)

    @warnings_system.subcommand(
        name="lista",
        description="Pokazuje dostępne informacje o ostrzeżeniach użytkownika.",
    )
    async def warn_list(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Wybierz osobę której chcesz sprawdzić ostrzeżenia.",
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings WHERE guild_id = ? and user_id = ?",
            (interaction.guild.id, member.id),
        )

        if not response or response[2] == "{}":
            return await interaction.send_error_message(
                description="Niestety, ale podana osoba nie posiada żadnych ostrzeżeń."
            )
        await interaction.response.defer()

        warnings_data: dict[str, str] = literal_eval(response[2])

        embed = Embed(
            title=f"Ostrzeżenia: {member.name} ({len(warnings_data)})",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        for index, warn_id in enumerate(warnings_data):
            embed.add_field(
                name=f"`📕` {index + 1}. Powód: {warnings_data[warn_id]}",
                value=f"{Emojis.REPLY.value} ID: `{warn_id}`",
                inline=False,
            )

            if index == 4:
                break

        pages_view = WarnsListView(warnings_data=warnings_data)

        await interaction.send(embed=embed, view=pages_view)

    @warnings_system.subcommand(  # pyright: ignore
        name="usuń_wszystkie",
        description="Resetuje wszystkie ostrzeżenia osobie lub na całym serwerze.",
    )
    @PermissionHandler(
        moderate_members=True,
        user_role_has_permission="warn",
    )
    async def warns_delete_all(
        self,
        interaction: CustomInteraction,
        choice: str = SlashOption(
            name="wybor",
            description="Wybierz spośród opcji.",
            choices={
                "Jednej osobie": "person",
                "Cały serwer": "all",
            },
        ),
    ):
        assert isinstance(interaction.user, Member)

        member: Optional[Member] = None

        if choice == "all":
            await interaction.response.defer()

        else:
            embed = Embed(
                title="<:people:992161973385035796> Sprecyzuj użytkownika",
                description=f"{Emojis.REPLY.value} Oznacz osobę, której chcesz wyczyścić ostrzeżenia. "
                f"\n**Na odpowiedź masz 2 minuty!**",
                color=Color.blue(),
                timestamp=utils.utcnow(),
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__}",
                icon_url=self.bot.avatar_url,
            )
            await interaction.send(embed=embed)

            try:
                member_message: Message = await self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user,
                    timeout=120,
                )

            except exceptions.TimeoutError:
                embed.title = "<:clock:992157767244714156> Konfiguracja wstrzymana."
                embed.description = "*Instalacja przerwana (Upłynął limit czasu).*"
                embed.colour = Color.red()
                embed.set_footer(
                    text=f"Smiffy v{self.bot.__version__}",
                    icon_url=self.bot.avatar_url,
                )
                return await interaction.edit_original_message(embed=embed)

            try:
                member: Optional[Member] = await MemberConverter().convert(
                    interaction,
                    member_message.content,  # pyright: ignore
                )

                if not member:
                    raise errors.MemberNotFound(member_message.content)

            except errors.MemberNotFound:
                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description="**Nie mogłem odnaleźć podanego użytkownika.** Spróbuj jeszcze raz.",
                )
                embed.set_author(
                    name=interaction.user,
                    icon_url=interaction.user_avatar_url,
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)
                embed.set_footer(
                    text=f"Smiffy v{self.bot.__version__}",
                    icon_url=self.bot.avatar_url,
                )
                return await interaction.edit_original_message(embed=embed)

            await member_message.delete()

        embed_description = (
            f"{Emojis.REPLY.value} Czy aby na pewno chcesz usunąć " f"**wszystkie ostrzeżenia** na serwerze"
        )
        if choice != "all":
            assert member

            embed_description: str = (
                f"{Emojis.REPLY.value} Czy aby na pewno chcesz usunąć "
                f"**wszystkie ostrzeżenia** osobie: {member.mention}"
            )

        embed = Embed(
            title="<:info1:953722089754472458> Potwierdz swój wybór",
            description=embed_description,
            color=Color.yellow(),
            timestamp=utils.utcnow(),
        )
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        buttons = DeleteAllWarnsView(
            interaction.user.id,
            self.bot,
            person=member,
        )

        if choice != "all":
            await interaction.edit_original_message(embed=embed, view=buttons)
        else:
            await interaction.send(embed=embed, view=buttons)


def setup(bot: Smiffy):
    bot.add_cog(CommandWarn(bot))
