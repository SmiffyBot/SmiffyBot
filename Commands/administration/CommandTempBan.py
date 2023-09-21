from __future__ import annotations

from asyncio import sleep
from time import time
from typing import TYPE_CHECKING, Iterable, Optional

from humanfriendly import InvalidTimespan, parse_timespan
from nextcord import (
    Color,
    Embed,
    Member,
    Object,
    SlashOption,
    errors,
    slash_command,
    utils,
)

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord import BanEntry, Guild

    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandTempBan(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot=bot)

        self.bot.loop.create_task(self.load_tempbans())

    @slash_command(
        name="tempban",
        description="Zbanuj użytkownika na określony czas!",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(ban_members=True, user_role_has_permission="tempban")
    async def tempban(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę, którą chcesz zbanować."),
        ban_duration: str = SlashOption(name="czas_blokady", description="Podaj czas bana np. 5m"),
        delete_messages: int = SlashOption(
            name="wiadomosci",
            description="Wybierz czy usuwać ostatnie wiadomości użytkownika",
            choices={"Ostatnie 7 dni": 7, "Ostatnie 24h": 1, "Nie usuwaj": 0},
        ),
        reason: Optional[str] = SlashOption(name="powod", description="Podaj powód bana", max_length=256),
    ):
        if not reason:
            reason = "Brak"

        if not isinstance(member, Member) or not isinstance(interaction.user, Member):
            # This should never happen, but discord sometimes messes things up - not sure why.

            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd. Kod: 51")

        assert delete_messages in (0, 1, 7) and self.bot.user and interaction.guild
        # Stuff for proper type checking

        await interaction.response.defer()

        if interaction.guild.me.top_role <= member.top_role or interaction.guild.owner_id == member.id:
            return await interaction.send_error_message(
                description=f"Użytkownik: {member.mention} posiada większe uprawnienia ode mnie.",
            )

        if interaction.user.top_role.position <= member.top_role.position:
            return await interaction.send_error_message(
                description=f"Posiadasz zbyt małe uprawnienia, aby zbanować: {member.mention}",
            )

        try:
            seconds: float = parse_timespan(ban_duration)
        except InvalidTimespan:
            return await interaction.send_error_message(
                description="Wpisałeś/aś niepoprawną jednostkę czasu\n> Przykład: 5m (5minut)",
            )

        embed = Embed(
            title="Pomyslnie zbanowano <a:success:984490514332139600>",
            timestamp=utils.utcnow(),
            color=Color.green(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.add_field(
            name="`👤` Użytkownik",
            value=f"{Emojis.REPLY.value} `{member}`",
            inline=False,
        )
        embed.add_field(name="`🗨️` Powód", value=f"{Emojis.REPLY.value} `{reason}`", inline=False)
        embed.add_field(
            name="`⏱️` Czas",
            value=f"{Emojis.REPLY.value} `{ban_duration}`",
            inline=False,
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.user.display_avatar.url,
        )

        try:
            await member.ban(reason=reason, delete_message_days=delete_messages)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return await interaction.send_error_message(description=f"Wystąpił nieoczekiwany błąd. {e}")

        await interaction.send(embed=embed)

        await self.bot.loop.create_task(self.unban_member(interaction.guild, member, seconds))

    async def send_dm_message(self, member: Member, root: Member, reason: str, ban_duration: str) -> None:
        assert self.bot.user

        embed = Embed(
            title=f"Zostałeś/aś zbanowany/a {Emojis.REDBUTTON.value}",
            timestamp=utils.utcnow(),
            color=Color.red(),
        )

        embed.set_author(name=root, icon_url=root.display_avatar.url)
        embed.set_thumbnail(url=Avatars.get_guild_icon(root.guild))

        embed.add_field(name="`👤` Administrator", value=f"{Emojis.REPLY.value} `{root}`")
        embed.add_field(name="`🗨️` Powód", value=f"{Emojis.REPLY.value} `{reason}`", inline=False)
        embed.add_field(
            name="`📌` Serwer",
            value=f"{Emojis.REPLY.value} `{root.guild.name}`",
            inline=False,
        )

        embed.add_field(name="`⏱️` Czas", value=f"{Emojis.REPLY.value} `{ban_duration}`")

        embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

        try:
            await member.send(embed=embed)
        except errors.Forbidden:
            pass

    async def unban_member(self, guild: Guild, member: Member, duration: float) -> None:
        """
        The unban_member function is used to unban a member from the guild.

        :param guild: Get the guild id
        :param member: Get the user id of the member that is being unbanned
        :param duration: Determine how long the member is banned for
        :return: None
        """

        ban_duration: int = int(time() + duration) + 7200

        await self.bot.db.execute_fetchone(
            "INSERT INTO tempbans(guild_id, user_id, ban_duration) VALUES(?,?,?)",
            (guild.id, member.id, ban_duration),
        )

        await sleep(duration)
        try:
            await guild.unban(user=member)
        except (errors.HTTPException, errors.Forbidden):
            pass

        await self.bot.db.execute_fetchone(
            "DELETE FROM tempbans WHERE guild_id = ? AND user_id = ?",
            (guild.id, member.id),
        )

    async def load_tempbans(self) -> None:
        """
        The load_tempbans function loads the bans stored in the database,
        then runs a function that waits the time of the ban and then unbans the person

        :return: None
        """

        await self.bot.wait_until_ready()

        async def delete_row(guild_id: int, member_id: int) -> None:
            """
            The delete_row function deletes a row from the tempbans table.

            :param guild_id: Identify the guild in which the user is banned
            :param member_id: Specify the user that is being unbanned
            :return: None
            """

            await self.bot.db.execute_fetchone(
                "DELETE FROM tempbans WHERE guild_id = ? AND user_id = ?",
                (guild_id, member_id),
            )

        async def unban_user(guild_to_unban: Guild, ban_entry: BanEntry, duration: int) -> None:
            if ban_entry.user:
                unix_now = time() + 7200
                seconds_diff: int = int(duration - unix_now)
                if seconds_diff > 1:
                    await sleep(seconds_diff)

                await guild_to_unban.unban(user=ban_entry.user)
                await delete_row(guild_id=guild_to_unban.id, member_id=ban_entry.user.id)

        response: Iterable[Optional[DB_RESPONSE]] = await self.bot.db.execute_fetchall(
            "SELECT * FROM tempbans"
        )

        if response:
            for data in response:
                if not data:
                    continue

                await sleep(0.5)

                # Format: data(guild_id, user_id, ban_duration)

                guild: Optional[Guild] = self.bot.get_guild(data[0])
                user_id: int = data[1]
                ban_duration: int = data[2]

                if not guild:
                    await delete_row(data[0], user_id)
                    continue

                try:
                    ban_object: Optional[BanEntry] = await guild.fetch_ban(Object(id=int(user_id)))
                except (errors.NotFound, errors.Forbidden):
                    await delete_row(data[0], user_id)
                    continue

                self.bot.loop.create_task(
                    unban_user(
                        guild_to_unban=guild,
                        ban_entry=ban_object,
                        duration=ban_duration,
                    )
                )


def setup(bot: Smiffy):
    bot.add_cog(CommandTempBan(bot))
