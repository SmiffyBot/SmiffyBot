from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Member, SlashOption

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import PlayerT


class CommandSetVolume(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="głośność",
        description="Zmienia głośność piosenki w %",
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_setvolume(
        self,
        interaction: CustomInteraction,
        volume: int = SlashOption(
            name="głośność",
            description="% głośności od 1 do 500",
        ),
    ):
        assert isinstance(interaction.user, Member)
        assert interaction.guild

        await interaction.response.defer()

        if volume <= 0:
            return await interaction.send_error_message(
                description="Poziom głośności nie może być niższy niż `1%`"
            )

        if volume > 500:
            return await interaction.send_error_message(
                description="Poziom głośności nie może być większy niż `500%`",
            )

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(
                description="Bot nie jest podłączony pod żaden kanał.",
            )

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
            )

        if not interaction.guild.voice_client:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        await player.set_volume(volume)

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Poziom głośności został ustawiony na `{volume}%`",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandSetVolume(bot))
