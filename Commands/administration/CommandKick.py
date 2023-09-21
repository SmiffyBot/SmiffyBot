from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Member, SlashOption, errors, slash_command, utils

from enums import Emojis
from utilities import Avatars, CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandKick(CustomCog):
    @slash_command(
        name="kick",
        description="Wyrzuć użytkownika!",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(
        ban_members=True,
        user_role_has_permission="kick",
    )
    async def kick(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj osobę, którą chcesz wyrzucić.",
        ),
        reason: Optional[str] = SlashOption(
            name="powod",
            description="Podaj powód",
            max_length=256,
        ),
    ):
        if not isinstance(member, Member) or not isinstance(interaction.user, Member):
            # This should never happen, but discord sometimes messes things up - not sure why.

            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd. Kod: 51")

        assert self.bot.user and interaction.guild
        # Stuff for proper type checking

        await interaction.response.defer()

        if interaction.guild.me.top_role <= member.top_role or interaction.guild.owner_id == member.id:
            return await interaction.send_error_message(
                description=f"Użytkownik: {member.mention} posiada większe uprawnienia ode mnie."
            )
        if (
            interaction.user.id != interaction.guild.owner_id
            and interaction.user.top_role.position <= member.top_role.position
        ):
            return await interaction.send_error_message(
                description=f"Posiadasz zbyt małe uprawnienia, aby wyrzucić: {member.mention}"
            )

        if not reason:
            reason = "Brak"

        embed = Embed(
            title=f"Pomyslnie wyrzucono {Emojis.GREENBUTTON.value}",
            timestamp=utils.utcnow(),
            color=Color.green(),
        )

        embed.add_field(
            name="`👤` Użytkownik",
            value=f"{Emojis.REPLY.value} `{member}`",
        )

        embed.add_field(
            name="`🗨️` Powód",
            value=f"{Emojis.REPLY.value} `{reason}`",
            inline=False,
        )

        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.user.display_avatar.url,
        )

        await self.send_dm_message(member, interaction.user, reason)
        await member.kick(reason=reason)
        await interaction.send(embed=embed)

    async def send_dm_message(
        self,
        member: Member,
        root: Member,
        reason: str,
    ) -> None:
        embed = Embed(
            title=f"Zostałeś/aś wyrzucony/a {Emojis.REDBUTTON.value}",
            timestamp=utils.utcnow(),
            color=Color.red(),
        )
        embed.set_author(
            name=root,
            icon_url=root.display_avatar.url,
        )
        embed.set_thumbnail(url=Avatars.get_guild_icon(root.guild))

        embed.add_field(
            name="`👤` Administrator",
            value=f"{Emojis.REPLY.value} `{root}`",
        )
        embed.add_field(
            name="`🗨️` Powód",
            value=f"{Emojis.REPLY.value} `{reason}`",
            inline=False,
        )
        embed.add_field(
            name="`📌` Serwer",
            value=f"{Emojis.REPLY.value} `{root.guild.name}`",
        )

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )

        try:
            await member.send(embed=embed)
        except errors.Forbidden:
            pass


def setup(bot: Smiffy):
    bot.add_cog(CommandKick(bot))
