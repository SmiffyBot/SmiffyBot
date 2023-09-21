from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from humanfriendly import InvalidTimespan, parse_timespan
from nextcord import Color, Embed, Member, SlashOption, errors, slash_command, utils
from nextcord.ext.application_checks import ApplicationMissingPermissions

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandMute(CustomCog):
    @slash_command(
        name="mute",
        description="Wycisz upierdliwego użytkownika :>",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(moderate_members=True, user_role_has_permission="mute")
    async def mute(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj użytkownika którego chcesz wyciszyć"),
        time: str = SlashOption(name="czas", description="Podaj na ile chcesz wyciszyć użytkownika. np. 5m"),
        reason: str = SlashOption(name="powod", description="Podaj powód wyciszenia"),
    ):
        if not isinstance(member, Member) or not isinstance(interaction.user, Member):
            # This should never happen, but discord sometimes messes things up - not sure why.

            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd. Kod: 51")

        assert self.bot.user and interaction.guild and interaction.user

        await interaction.response.defer()

        if member.communication_disabled_until:
            command_unmute_mention: str = interaction.get_command_mention(command_name="unmute")

            return await interaction.send_error_message(
                description=f"{member.mention} już posiada wyciszenie. Użyj {command_unmute_mention}, aby odciszyć.",
            )

        if interaction.guild.me.top_role <= member.top_role:
            return await interaction.send_error_message(
                description=f"Użytkownik: {member.mention} posiada wyższą role ode mnie.",
            )

        if interaction.user.top_role <= member.top_role or member.id == interaction.guild.owner_id:
            return await interaction.send_error_message(
                description=f"Twoja rola jest zbyt nisko, aby wyciszyć {member.mention}",
            )

        try:
            duration = parse_timespan(time)
        except InvalidTimespan:
            return await interaction.send_error_message(
                description="> Podałeś niepoprawną jednostkę czasu.\n Przykład: `5m` ||5minut||",
            )

        try:
            await member.edit(timeout=timedelta(seconds=duration))
        except (ApplicationMissingPermissions, errors.Forbidden):
            return await interaction.send_error_message(
                description=f"**Użytkownik: {member.mention} posiada zbyt duże uprawnienia**",
            )

        embed = Embed(
            title=f"Pomyślnie wyciszono {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.add_field(name="`👤` Użytkownik", value=f"{Emojis.REPLY.value} `{member}`")
        embed.add_field(name="`🗨️`  Powód", value=f"{Emojis.REPLY.value} `{reason}`", inline=False)
        embed.add_field(name="`⏱️` Czas", value=f"{Emojis.REPLY.value} `{time}`", inline=False)
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.user.display_avatar.url,
        )

        await self.send_dm_message(member=member, root=interaction.user, reason=reason, duration=time)

        await interaction.send(embed=embed)

    async def send_dm_message(self, member: Member, root: Member, reason: str, duration: str) -> None:
        embed = Embed(
            title=f"Zostałeś/aś wyciszony/a {Emojis.REDBUTTON.value}",
            color=Color.red(),
            timestamp=utils.utcnow(),
        )

        embed.add_field(name="`👤` Administrator", value=f"{Emojis.REPLY.value} `{root}`")
        embed.add_field(name="`🗨️` Powód", value=f"{Emojis.REPLY.value} `{reason}`", inline=False)
        embed.add_field(
            name="`📌` Serwer",
            value=f"{Emojis.REPLY.value} `{root.guild.name}`",
            inline=False,
        )

        embed.add_field(name="`⏱️` Czas", value=f"{Emojis.REPLY.value} `{duration}`")

        embed.set_thumbnail(url=Avatars.get_guild_icon(member.guild))
        embed.set_author(name=root, icon_url=Avatars.get_user_avatar(root))

        embed.set_footer(text=f"Smiffy v{self.bot.__version__}", icon_url=self.bot.avatar_url)

        try:
            await member.send(embed=embed)
        except errors.Forbidden:
            pass


def setup(bot: Smiffy):
    bot.add_cog(CommandMute(bot))
