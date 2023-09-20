from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import Member
from enums import Emojis
from utilities import CustomInteraction, CustomCog, PermissionHandler

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import PlayerT
    from mafic import Track


class CommandSkip(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="skip", description="Pomija aktualną graną piosenke"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_skip(self, interaction: CustomInteraction):
        assert interaction.guild
        assert isinstance(interaction.user, Member)

        await interaction.response.defer()

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
            )

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
            )

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            return await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
            )

        if not interaction.guild.voice_client:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        if player.loop:
            return await interaction.send_error_message(
                description="Najpierw musisz wyłączyć zapętlanie piosenki."
            )

        current_track: Optional[Track] = player.current

        if not current_track:
            return await interaction.send_error_message(description="Bot aktualnie nic nie gra.")

        await player.stop()

        await interaction.send_success_message(
            title=f"Pomyślnie pominięto piosenke {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pominięta piosenka: [`LINK`]({current_track.uri})",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandSkip(bot))
