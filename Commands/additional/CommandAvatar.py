from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import (
    Color,
    Embed,
    Member,
    SlashOption,
    slash_command,
    user_command,
    utils,
)

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy


class CommandAvatar(CustomCog):
    @user_command(name="avatar")
    async def avatar_application(
        self,
        interaction: CustomInteraction,
        member: Member,
    ) -> None:
        await self.avatar(interaction, member)

    @slash_command(
        name="avatar",
        description="Wyświetli avatar użytkownika",
        dm_permission=False,
    )
    async def avatar(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj użytkownika",
            required=False,
        ),
    ):
        assert interaction.guild

        user: Member = member or interaction.user

        embed = Embed(
            title=f"Avatar: {user.name}",
            description=f"[LINK]({user.display_avatar.url})",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_image(url=user.display_avatar.url)
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild_icon_url,
        )
        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandAvatar(bot))
