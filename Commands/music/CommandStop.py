from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Member

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import PlayerT


class CommandStop(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="stop", description="Wyłącza wszystkie piosenki"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_stop(self, interaction: CustomInteraction):
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

        player.queue = []
        await player.stop()

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono muzykę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Wszystkie piosenki zostały wyłączone.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandStop(bot))
