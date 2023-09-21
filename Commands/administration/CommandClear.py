from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import (
    Color,
    Embed,
    SlashOption,
    TextChannel,
    Thread,
    errors,
    slash_command,
    utils,
)

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandClear(CustomCog):
    @slash_command(
        name="clear", description="Usuń masowo wiadomości z kanału", dm_permission=False
    )  # pyright: ignore
    @PermissionHandler(ban_members=True, user_role_has_permission="clear")
    async def clear(
        self,
        interaction: CustomInteraction,
        times: int = SlashOption(
            name="ilość",
            description="Wpisz ilość wiadomości do usunięcia.",
        ),
    ):
        if not interaction.channel:
            # This should never have happened, but whatever.

            return await interaction.send_error_message(
                description="Wystąpił nieoczekiwany błąd. Spróbuj ponownie."
            )

        assert isinstance(interaction.channel, (Thread, TextChannel))
        # Type checking stuff

        if times > 1000 or times < 1:
            return await interaction.send_error_message(
                "**Podałeś/aś zbyt małą lub zbyt dużą ilość.**\n> Min `1` -> Max `1000`"
            )

        await interaction.send_success_message(title="Rozpoczynam usuwanie...", ephemeral=True)

        try:
            await interaction.channel.purge(limit=times)
        except errors.Forbidden:
            pass

        embed = Embed(
            title=f"Pomyślnie usunięto wiadomości {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"**{Emojis.REPLY.value} Usunięte wiadomości: `{times}`**",
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_footer(text="Wiadomość zostanie usunięta za 10s")
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        await interaction.channel.send(embed=embed, delete_after=10)


def setup(bot: Smiffy):
    bot.add_cog(CommandClear(bot))
