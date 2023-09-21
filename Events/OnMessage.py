from __future__ import annotations

from ast import literal_eval
from asyncio import sleep
from datetime import datetime, timedelta
from io import BytesIO
from random import randint
from re import Match, search
from time import time as now
from typing import TYPE_CHECKING, Awaitable, Callable, Iterable, Optional

from humanfriendly import parse_timespan
from nextcord import (
    ButtonStyle,
    Color,
    Embed,
    File,
    Guild,
    Member,
    TextChannel,
    errors,
    ui,
    utils,
)

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction

if TYPE_CHECKING:
    from nextcord import Emoji, Message, Role, Thread
    from nextcord.abc import GuildChannel

    from bot import Smiffy
    from typings import DB_RESPONSE


class DeleteMessageView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(  # pyright: ignore
        label="Usuń wiadomość",
        style=ButtonStyle.grey,
        emoji=Emojis.REDBUTTON.value,
        custom_id="antylink-deletemessage",
    )
    async def cancel(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        await interaction.response.defer()

        try:
            await interaction.delete_original_message()

            if interaction.message:
                await interaction.message.delete()
        except errors.NotFound:
            pass

    async def interaction_check(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        if interaction.user.guild_permissions.manage_messages:
            return True

        await interaction.send_error_message(
            description="Aby tego użyć musisz posiadać permisje: `Manage Messages`",
            ephemeral=True,
        )

        return False


class Punishments:
    def __init__(self, message: Message, bot: Smiffy) -> None:
        self.message: Message = message
        self.bot: Smiffy = bot

        self.user: Member = message.author  # pyright: ignore
        self.guild: Guild = message.guild  # pyright: ignore

        self.view_message: DeleteMessageView = DeleteMessageView()

    async def unban_member(
        self,
        guild: Guild,
        member: Member,
        duration: float,
    ) -> None:
        ban_duration: int = int(now() + duration) + 7200

        await self.bot.db.execute_fetchone(
            "INSERT INTO tempbans(guild_id, user_id, ban_duration) VALUES(?,?,?)",
            (guild.id, member.id, ban_duration),
        )

        await sleep(duration)

        try:
            await guild.unban(user=member)
        except (
            errors.HTTPException,
            errors.Forbidden,
        ):
            pass

        await self.bot.db.execute_fetchone(
            "DELETE FROM tempbans WHERE guild_id = ? AND user_id = ?",
            (guild.id, member.id),
        )

    async def handle_warning_punishment(
        self,
        punishment_data: dict[str, tuple[str, str]],
        member_warns: dict,
    ):
        embed = Embed(
            title="`🛠️` Kary za ostrzeżenia",
            timestamp=utils.utcnow(),
            color=Color.dark_theme(),
        )
        embed.set_author(
            name=self.user,
            icon_url=Avatars.get_user_avatar(self.user),
        )
        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

        for (
            warn_count,
            action_data,
        ) in punishment_data.items():
            if int(warn_count) == len(member_warns):
                action, time = action_data

                if action == "mute":
                    duration: float = parse_timespan(time)

                    try:
                        await self.user.edit(timeout=timedelta(seconds=duration))

                        pv_embed = Embed(
                            title=f"Zostałeś/aś wyciszony/a {Emojis.REDBUTTON.value}",
                            color=Color.red(),
                            timestamp=utils.utcnow(),
                        )

                        pv_embed.add_field(
                            name="`👤` Administrator",
                            value=f"{Emojis.REPLY.value} `Smiffy`",
                        )
                        pv_embed.add_field(
                            name="`🗨️` Powód",
                            value=f"{Emojis.REPLY.value} `Osiągnięcie {warn_count} ostrzeżeń`",
                            inline=False,
                        )
                        pv_embed.add_field(
                            name="`📌` Serwer",
                            value=f"{Emojis.REPLY.value} `{self.guild.name}`",
                            inline=False,
                        )

                        pv_embed.add_field(
                            name="`⏱️` Czas",
                            value=f"{Emojis.REPLY.value} `{time}`",
                        )

                        pv_embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))
                        pv_embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )

                        embed.set_footer(
                            text=f"Smiffy v{self.bot.__version__}",
                            icon_url=self.bot.avatar_url,
                        )

                        try:
                            await self.user.send(embed=pv_embed)
                        except errors.Forbidden:
                            pass

                        embed.description = (
                            f"{Emojis.REPLY.value} {self.user.mention} otrzymał karę: `Mute` za "
                            f"**{warn_count}** warny na czas: `{time}`."
                        )

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except errors.Forbidden:
                            pass

                    except errors.Forbidden:
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                            description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `Mute` za `{warn_count}` "
                            f"warny. \n\n*Użytkownik posiada większe uprawnienia od bota.*",
                        )
                        embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )
                        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except (
                            errors.Forbidden,
                            errors.HTTPException,
                        ):
                            pass

                    return

                if action == "tempban":
                    duration: float = parse_timespan(time)

                    try:
                        if self.guild.owner_id == self.user:
                            raise KeyError

                        if self.user.top_role.position >= self.guild.me.top_role.position:
                            raise KeyError

                        pv_embed = Embed(
                            title=f"Zostałeś/aś zbanowany/a {Emojis.REDBUTTON.value}",
                            timestamp=utils.utcnow(),
                            color=Color.red(),
                        )
                        pv_embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )
                        pv_embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        pv_embed.add_field(
                            name="`👤` Administrator",
                            value=f"{Emojis.REPLY.value} `Smiffy`",
                        )
                        pv_embed.add_field(
                            name="`🗨️` Powód",
                            value=f"{Emojis.REPLY.value} `Osiągnięcie {warn_count} ostrzeżeń`",
                            inline=False,
                        )

                        pv_embed.add_field(
                            name="`📌` Serwer",
                            value=f"{Emojis.REPLY.value} `{self.guild.name}`",
                            inline=False,
                        )

                        pv_embed.add_field(
                            name="`⏱️` Czas",
                            value=f"{Emojis.REPLY.value} `{time}`",
                        )

                        pv_embed.set_footer(
                            text=f"Smiffy v{self.bot.__version__}",
                            icon_url=self.bot.avatar_url,
                        )

                        try:
                            await self.user.send(embed=pv_embed)
                        except errors.Forbidden:
                            pass

                        await self.user.ban(reason="KaryWarny - Smiffy")

                        await self.unban_member(
                            self.guild,
                            self.user,
                            duration,
                        )

                        embed.description = (
                            f"{Emojis.REPLY.value} {self.user.mention} otrzymał karę: `TempBan` za "
                            f"**{warn_count}** warny na czas: `{time}`."
                        )

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except errors.Forbidden:
                            pass

                    except (
                        errors.Forbidden,
                        KeyError,
                    ):
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                            description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `TempBan` za `{warn_count}`"
                            f" warny. \n\n*Użytkownik posiada większe uprawnienia od bota.*",
                        )
                        embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )
                        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except (
                            errors.Forbidden,
                            errors.HTTPException,
                        ):
                            pass

                    return

                if action == "kick":
                    try:
                        if self.guild.owner_id == self.user:
                            raise KeyError

                        if self.user.top_role.position >= self.guild.me.top_role.position:
                            raise KeyError

                        pv_embed = Embed(
                            title=f"Zostałeś/aś wyrzucony/a {Emojis.REDBUTTON.value}",
                            timestamp=utils.utcnow(),
                            color=Color.red(),
                        )
                        pv_embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )
                        pv_embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        pv_embed.add_field(
                            name="`👤` Administrator",
                            value=f"{Emojis.REPLY.value} `Smiffy`",
                        )
                        pv_embed.add_field(
                            name="`🗨️` Powód",
                            value=f"{Emojis.REPLY.value} `Osiągnięcie {warn_count} ostrzeżeń`",
                            inline=False,
                        )

                        pv_embed.add_field(
                            name="`📌` Serwer",
                            value=f"{Emojis.REPLY.value} `{self.guild.name}`",
                            inline=False,
                        )

                        pv_embed.set_footer(
                            text=f"Smiffy v{self.bot.__version__}",
                            icon_url=self.bot.avatar_url,
                        )

                        try:
                            await self.user.send(embed=pv_embed)
                        except errors.Forbidden:
                            pass

                        await self.user.kick(reason="KaryWarny - Smiffy")

                        embed.description = (
                            f"{Emojis.REPLY.value} {self.user.mention} otrzymał karę: `Kick` za "
                            f"**{warn_count}** warny."
                        )

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except errors.Forbidden:
                            pass

                    except (
                        errors.Forbidden,
                        KeyError,
                    ):
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                            description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `Kick` za `{warn_count}`"
                            f" warny. \n\n*Użytkownik posiada większe uprawnienia od bota.*",
                        )
                        embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )
                        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except (
                            errors.Forbidden,
                            errors.HTTPException,
                        ):
                            pass

                    return

                if action == "ban":
                    try:
                        if self.guild.owner_id == self.user:
                            raise KeyError

                        if self.user.top_role.position >= self.guild.me.top_role.position:
                            raise KeyError

                        pv_embed = Embed(
                            title=f"Zostałeś/aś zbanowany/a {Emojis.REDBUTTON.value}",
                            timestamp=utils.utcnow(),
                            color=Color.red(),
                        )
                        pv_embed.set_author(
                            name=self.user,
                            icon_url=Avatars.get_user_avatar(self.user),
                        )
                        pv_embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        pv_embed.add_field(
                            name="`👤` Administrator",
                            value=f"{Emojis.REPLY.value} `Smiffy`",
                        )
                        pv_embed.add_field(
                            name="`🗨️` Powód",
                            value=f"{Emojis.REPLY.value} `Osiągnięcie {warn_count} ostrzeżeń`",
                            inline=False,
                        )

                        pv_embed.add_field(
                            name="`📌` Serwer",
                            value=f"{Emojis.REPLY.value} `{self.guild.name}`",
                            inline=False,
                        )

                        pv_embed.set_footer(
                            text=f"Smiffy v{self.bot.__version__}",
                            icon_url=self.bot.avatar_url,
                        )

                        try:
                            await self.user.send(embed=pv_embed)
                        except errors.Forbidden:
                            pass

                        await self.user.ban(reason="KaryWarny - Smiffy")

                        embed.description = (
                            f"{Emojis.REPLY.value} {self.user.mention} otrzymał karę: `Ban` za "
                            f"**{warn_count}** warny."
                        )

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except errors.Forbidden:
                            pass

                    except (
                        errors.Forbidden,
                        KeyError,
                    ):
                        embed = Embed(
                            title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                            colour=Color.red(),
                            timestamp=utils.utcnow(),
                            description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `Ban` za `{warn_count}`"
                            f" warny. \n\n*Użytkownik posiada większe uprawnienia od bota.*",
                        )
                        embed.set_author(
                            name=self.user,
                            icon_url=self.user.display_avatar.url,
                        )
                        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                        try:
                            await self.message.channel.send(
                                embed=embed,
                                view=self.view_message,
                            )
                        except (
                            errors.Forbidden,
                            errors.HTTPException,
                        ):
                            pass

                    return

    async def kick(self):
        try:
            if self.guild.owner_id == self.user:
                raise KeyError

            if self.user.top_role.position >= self.guild.me.top_role.position:
                raise KeyError

            embed = Embed(
                title=f"Zostałeś/aś wyrzucony/a {Emojis.REDBUTTON.value}",
                timestamp=utils.utcnow(),
                color=Color.red(),
            )
            embed.set_author(
                name=self.user,
                icon_url=Avatars.get_user_avatar(self.user),
            )
            embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

            embed.add_field(
                name="`👤` Administrator",
                value=f"{Emojis.REPLY.value} `Smiffy`",
            )
            embed.add_field(
                name="`🗨️` Powód",
                value=f"{Emojis.REPLY.value} `System Antylink`",
                inline=False,
            )
            embed.add_field(
                name="`📌` Serwer",
                value=f"{Emojis.REPLY.value} `{self.guild.name}`",
            )

            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__}",
                icon_url=self.bot.avatar_url,
            )

            try:
                await self.user.send(embed=embed)
            except errors.Forbidden:
                pass

            await self.user.kick(reason="Antylink - Smiffy")

        except (errors.Forbidden, KeyError):
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                colour=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `Kick` osobie: {self.user.mention}."
                f"\n\n*Użytkownik posiada większe uprawnienia od bota.*",
            )
            embed.set_author(
                name=self.user,
                icon_url=Avatars.get_user_avatar(self.user),
            )
            embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

            try:
                await self.message.channel.send(
                    embed=embed,
                    view=self.view_message,
                )
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass
            return

        embed = Embed(
            title=f"Pomyślnie nadano karę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Kara `Kick` za Antylink została nadana.",
            timestamp=utils.utcnow(),
            color=Color.dark_theme(),
        )
        embed.set_author(
            name=self.user,
            icon_url=Avatars.get_user_avatar(self.user),
        )
        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

        try:
            await self.message.channel.send(
                embed=embed,
                view=self.view_message,
            )
        except (
            errors.Forbidden,
            errors.HTTPException,
        ):
            pass

    async def ban(self):
        try:
            if self.guild.owner_id == self.user:
                raise KeyError

            if self.user.top_role.position >= self.guild.me.top_role.position:
                raise KeyError

            embed = Embed(
                title=f"Zostałeś/aś zbanowany/a {Emojis.REDBUTTON.value}",
                timestamp=utils.utcnow(),
                color=Color.red(),
            )
            embed.set_author(
                name=self.user,
                icon_url=Avatars.get_user_avatar(self.user),
            )
            embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

            embed.add_field(
                name="`👤` Administrator",
                value=f"{Emojis.REPLY.value} `Smiffy`",
            )
            embed.add_field(
                name="`🗨️` Powód",
                value=f"{Emojis.REPLY.value} `System Antylink`",
                inline=False,
            )
            embed.add_field(
                name="`📌` Serwer",
                value=f"{Emojis.REPLY.value} `{self.guild.name}`",
            )

            embed.set_footer(
                text=f"Smiffy v{self.bot.__version__}",
                icon_url=self.bot.avatar_url,
            )

            try:
                await self.user.send(embed=embed)
            except errors.Forbidden:
                pass

            await self.user.ban(reason="Antylink - Smiffy")

        except (errors.Forbidden, KeyError):
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                colour=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `Ban` osobie: {self.user.mention}."
                f"\n\n*Użytkownik posiada większe uprawnienia od bota.*",
            )
            embed.set_author(
                name=self.user,
                icon_url=Avatars.get_user_avatar(self.user),
            )
            embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

            try:
                await self.message.channel.send(
                    embed=embed,
                    view=self.view_message,
                )
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass

            return

        embed = Embed(
            title=f"Pomyślnie nadano karę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Kara `Ban` za Antylink została nadana.",
            timestamp=utils.utcnow(),
            color=Color.dark_theme(),
        )
        embed.set_author(
            name=self.user,
            icon_url=Avatars.get_user_avatar(self.user),
        )
        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

        try:
            await self.message.channel.send(
                embed=embed,
                view=self.view_message,
            )
        except (
            errors.Forbidden,
            errors.HTTPException,
        ):
            pass

    async def add_warn(self):
        try:
            if self.guild.owner_id == self.user.id:
                raise KeyError

            if self.user.top_role.position >= self.guild.me.top_role.position:
                raise KeyError

        except KeyError:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                colour=Color.red(),
                timestamp=utils.utcnow(),
                description=f"{Emojis.REPLY.value} Bot nie mógł nadać kary: `Warn` osobie: {self.user.mention}."
                f"\n\n*Użytkownik posiada większe uprawnienia od bota.*",
            )
            embed.set_author(
                name=self.user,
                icon_url=Avatars.get_user_avatar(self.user),
            )
            embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

            try:
                await self.message.channel.send(
                    embed=embed,
                    view=self.view_message,
                )
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass

            return

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings WHERE guild_id = ? and user_id = ?",
            (self.guild.id, self.user.id),
        )

        if response:
            member_warns: dict = literal_eval(str(response[2]))

            if len(member_warns) >= 50:
                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                    colour=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Osoba {self.user.mention} osiągnęła limit `50` ostrzeżeń.",
                )
                embed.set_author(
                    name=self.user,
                    icon_url=Avatars.get_user_avatar(self.user),
                )
                embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

                try:
                    await self.message.channel.send(
                        embed=embed,
                        view=self.view_message,
                    )
                except (
                    errors.Forbidden,
                    errors.HTTPException,
                ):
                    pass
                return

            new_warn_id: str = f"sf-{randint(10000, 99999)}{str(self.user.id)[0:3]}"

            while new_warn_id in member_warns.keys():
                new_warn_id: str = f"sf-{randint(10000, 99999)}{str(self.user.id)[0:3]}"

            member_warns[new_warn_id] = "Smiffy - AntyLink"

            await self.bot.db.execute_fetchone(
                "UPDATE warnings SET warns = ? WHERE guild_id = ? and user_id = ?",
                (
                    str(member_warns),
                    self.guild.id,
                    self.user.id,
                ),
            )

        else:
            new_warn: dict = {f"sf-{randint(10000, 99999)}{str(self.user.id)[0:3]}": "Smiffy - AntyLink"}

            member_warns: dict = new_warn

            await self.bot.db.execute_fetchone(
                "INSERT INTO warnings(guild_id, user_id, warns) VALUES(?,?,?)",
                (
                    self.guild.id,
                    self.user.id,
                    str(new_warn),
                ),
            )

        embed = Embed(
            title=f"Pomyślnie nadano karę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Kara `Warn` za Antylink została nadana.",
            timestamp=utils.utcnow(),
            color=Color.dark_theme(),
        )
        embed.set_author(
            name=self.user,
            icon_url=Avatars.get_user_avatar(self.user),
        )
        embed.set_thumbnail(url=Avatars.get_guild_icon(self.guild))

        try:
            await self.message.channel.send(
                embed=embed,
                view=self.view_message,
            )
        except (
            errors.Forbidden,
            errors.HTTPException,
        ):
            pass

        warnings_punishments_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM warnings_punishments WHERE guild_id = ?",
            (self.guild.id,),
        )

        if not warnings_punishments_response:
            return

        punishment_data: dict[str, tuple[str, str]] = literal_eval(warnings_punishments_response[1])

        await self.handle_warning_punishment(punishment_data, member_warns)


class OnMessageEvent(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot)

        self.regex: str = (
            r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s"
            r"()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\(["
            r"^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
        )

        self.bot.loop.create_task(self.load_button_view())

    async def load_button_view(self):
        self.bot.add_view(DeleteMessageView())

    async def handle_antylink(self, message: Message) -> bool:
        assert message.guild and isinstance(message.author, Member)

        if not message.author.guild_permissions.manage_messages:
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM antylink WHERE guild_id = ?",
                (message.guild.id,),
            )
            if response:
                result: Optional[Match] = search(self.regex, message.content)
                if result:
                    punishments: Punishments = Punishments(message, self.bot)

                    punishments_data: dict[
                        str,
                        Callable[[], Awaitable[None]],
                    ] = {
                        "kick": punishments.kick,
                        "ban": punishments.ban,
                        "warn": punishments.add_warn,
                    }

                    punishment: str = response[1]

                    embed = Embed(
                        title="`⛔` Wykryto link!",
                        color=Color.red(),
                        description=f"{Emojis.REPLY.value} Link wysłany przez: {message.author.mention}",
                        timestamp=utils.utcnow(),
                    )
                    embed.set_author(
                        name=message.author,
                        icon_url=self.avatars.get_user_avatar(message.author),
                    )
                    embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))

                    embed.set_footer(
                        text=f"Smiffy v{self.bot.__version__}",
                        icon_url=self.bot.avatar_url,
                    )

                    button = DeleteMessageView()
                    await message.channel.send(embed=embed, view=button)

                    await message.delete()

                    if punishment != "brak":
                        await punishments_data[punishment]()

                    return True

        return False

    async def handle_antyflood(self, message: Message):
        assert isinstance(message.author, Member) and message.guild

        if not message.author.guild_permissions.manage_messages:
            response_antyflood: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM antyflood WHERE guild_id = ?",
                (message.guild.id,),
            )
            if response_antyflood:
                same_message: int = 0

                async for _message in message.channel.history(
                    after=datetime.utcnow() + timedelta(hours=2, minutes=-5)
                ):
                    if message.content == _message.content:
                        same_message += 1

                L: int = response_antyflood[1]
                if same_message > L:
                    await message.delete()

                    embed = Embed(
                        title=f"Twoja wiadomość została usunięta {Emojis.REDBUTTON.value}",
                        color=Color.red(),
                        description=f"{Emojis.REPLY.value} Zauważyłem, że wysłałeś `{L}` takich samych wiadomości "
                        f"w ciągu **5** minut.\n- W celu bezpieczeństwa usunąłem twoją wiadomość.",
                        timestamp=utils.utcnow(),
                    )
                    embed.set_author(
                        name=message.author,
                        icon_url=self.avatars.get_user_avatar(message.author),
                    )
                    embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))

                    try:
                        await message.author.send(embed=embed)
                    except errors.Forbidden:
                        pass
                return True

        return False

    async def handle_suggestions(self, message: Message, comments: str):
        await message.delete()

        embed = Embed(
            title="<a:ping:987762816062726224> Nowa propozycja!",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} **{message.content}**",
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))
        embed.set_author(
            name=message.author,
            icon_url=self.avatars.get_user_avatar(message.author),
        )
        embed.set_footer(text="Głosowanie: 0%")

        suggestion_message: Message = await message.channel.send(embed=embed)

        like: Optional[Emoji] = self.bot.get_emoji(951968571540529233)
        dislike: Optional[Emoji] = self.bot.get_emoji(951968542083932250)

        if like:
            await suggestion_message.add_reaction(like)

        if dislike:
            await suggestion_message.add_reaction(dislike)

        if comments == "on":
            thread: Thread = await suggestion_message.create_thread(
                name="Komentarze",
                auto_archive_duration=1440,
            )
            await thread.send(content="W tym wątku możecie dodawać komentarze dotyczące propozycji.")

    async def handle_autoresponder(self, message: Message):
        assert message.guild

        response_responder: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM autoresponder WHERE guild_id = ?",
            (message.guild.id,),
        )
        file: Optional[File] = None

        if response_responder:
            for data in response_responder:
                if data[4]:
                    image_data: BytesIO = BytesIO(data[4])
                    file = File(
                        image_data,
                        "autoresponder.png",
                    )

                if data[2] == "in" and data[1].lower() in message.content.lower():
                    await message.reply(content=data[3], file=file)
                    break

                if data[2] == "start" and message.content.lower().startswith(data[1].lower()):
                    await message.reply(content=data[3], file=file)
                    break

                if data[2] == "equals" and message.content.lower() == data[1].lower():
                    await message.reply(content=data[3], file=file)
                    break

    async def handle_leveling(self, message: Message):
        assert message.guild and isinstance(message.author, Member)

        def format_notify_message(content: str, new_level: int) -> str:
            content = (
                content.replace("{level}", str(new_level))
                .replace("{user}", message.author.name)
                .replace(
                    "{user.mention}",
                    message.author.mention,
                )
            )

            return content

        response_levels_data: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM levels WHERE guild_id = ?",
            (message.guild.id,),
        )

        if response_levels_data:
            response_users_data: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT * FROM levels_users WHERE guild_id = ? AND user_id = ?",
                (
                    message.guild.id,
                    message.author.id,
                ),
            )

            if not response_users_data:
                await self.bot.db.execute_fetchone(
                    "INSERT INTO levels_users(guild_id, user_id, level, xp) VALUES(?,?,?,?)",
                    (
                        message.guild.id,
                        message.author.id,
                        1,
                        0,
                    ),
                )
                return

            multiplier: int = 5
            user_roles_id: list[int] = [role.id for role in message.author.roles]

            if response_levels_data[3]:  # multiplier data
                multiplier_data: dict[int, int] = literal_eval(response_levels_data[3])

                for (
                    role_id,
                    role_multiplier,
                ) in multiplier_data.items():
                    if role_id in user_roles_id:
                        if role_multiplier > multiplier:
                            multiplier = role_multiplier

            level, xp = (
                response_users_data[2],
                response_users_data[3],
            )
            xp += multiplier
            next_level_xp: int = level * 50

            if xp < next_level_xp:
                await self.bot.db.execute_fetchone(
                    "UPDATE levels_users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
                    (
                        xp,
                        level,
                        message.guild.id,
                        message.author.id,
                    ),
                )
                return

            level += 1
            xp = 0

            await self.bot.db.execute_fetchone(
                "UPDATE levels_users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
                (
                    xp,
                    level,
                    message.guild.id,
                    message.author.id,
                ),
            )

            if response_levels_data[2]:  # notify data
                alerts_data: dict[str, str | int] = literal_eval(response_levels_data[2])
                notify_content: str = str(alerts_data["notify_content"])
                formatted_message: str = format_notify_message(notify_content, level)

                if alerts_data["type"] == "dm":
                    try:
                        await message.author.send(formatted_message)
                    except errors.Forbidden:
                        pass

                elif alerts_data["type"] == "channel":
                    channel_id: int = int(alerts_data["channel_id"])

                    channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

                    if isinstance(channel, TextChannel):
                        try:
                            await channel.send(formatted_message)
                        except errors.Forbidden:
                            pass
                else:
                    channel_id: int = int(alerts_data["channel_id"])

                    channel: Optional[GuildChannel] = await self.bot.getch_channel(channel_id)

                    try:
                        await message.author.send(formatted_message)
                    except errors.Forbidden:
                        pass

                    try:
                        if isinstance(channel, TextChannel):
                            await channel.send(formatted_message)
                    except errors.Forbidden:
                        pass

            if response_levels_data[1]:  # roles_data
                roles_data: dict[int, int] = literal_eval(response_levels_data[1])

                for (
                    role_level,
                    role_id,
                ) in roles_data.items():
                    if role_level == level:
                        role_mention: str = "Deleted role"

                        try:
                            role: Optional[Role] = await self.bot.getch_role(
                                message.guild,
                                role_id,
                            )

                            if not role:
                                raise AttributeError

                            role_mention: str = role.mention

                            await message.author.add_roles(
                                role,
                                reason="Levelowanie - Smiffy",
                            )

                        except errors.Forbidden:
                            embed = Embed(
                                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                                color=Color.red(),
                                timestamp=utils.utcnow(),
                                description=f"{Emojis.REPLY.value} Nie udało się nadać roli: {role_mention} za "
                                f"level `{level}`.\n**(Rola posiada większe uprawnienia od bota)**",
                            )
                            embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))

                            embed.set_author(
                                name=message.author,
                                icon_url=self.avatars.get_user_avatar(message.author),
                            )

                            try:
                                await message.channel.send(embed=embed)
                            except errors.Forbidden:
                                pass

                        except (
                            AttributeError,
                            errors.NotFound,
                        ):
                            embed = Embed(
                                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                                color=Color.red(),
                                timestamp=utils.utcnow(),
                                description=f"{Emojis.REPLY.value} Nie udało się nadać roli: {role_mention}"
                                f" za level `{level}`.\n**(Rola nie istnieje)**",
                            )
                            embed.set_thumbnail(url=self.avatars.get_guild_icon(message.guild))

                            embed.set_author(
                                name=message.author,
                                icon_url=self.avatars.get_user_avatar(message.author),
                            )

                            try:
                                await message.channel.send(embed=embed)
                            except errors.Forbidden:
                                pass

    @CustomCog.listener()
    async def on_message(self, message: Message):
        assert self.bot.user

        if not isinstance(message.author, Member):
            return

        if self.bot.user.mentioned_in(message) and not message.author.bot:
            if not message.mention_everyone or self.bot.user.mention in message.content:
                self.bot.dispatch("bot_mention", message)

        if not message.guild or message.author.bot:
            return

        if await self.handle_antylink(message):
            return

        if await self.handle_antyflood(message):
            return

        suggestions_response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM suggestions WHERE guild_id = ?",
            (message.guild.id,),
        )

        if suggestions_response and suggestions_response[1] == message.channel.id:
            await self.handle_suggestions(message, suggestions_response[2])

        else:
            await self.handle_autoresponder(message)

        await self.handle_leveling(message)


def setup(bot: Smiffy):
    bot.add_cog(OnMessageEvent(bot))
