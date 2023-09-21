from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Member

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import PlayerT


class CommandLoop(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="zapętlanie",
        description="Wyłącza lub włącza zapętlanie piosenki",
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_loop(self, interaction: CustomInteraction):
        assert interaction.guild and isinstance(interaction.user, Member)

        await interaction.response.defer()

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            await interaction.send_error_message(
                description="Bot nie jest aktualnie podłączony pod żaden kanał.",
            )
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
            )
            return

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
            )
            return

        if not interaction.guild.voice_client:
            await interaction.send_error_message(description="Bot aktualnie nic nie gra.")
            return

        player: PlayerT = interaction.guild.voice_client  # pyright: ignore
        assert isinstance(player, MusicPlayer)

        if player.loop:
            player.loop = False

            await interaction.send_success_message(
                title=f"Pomyślnie wyłączono zapętlanie {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Zapętlanie zostało wyłączone.",
            )

        else:
            player.loop = True

            await interaction.send_success_message(
                title=f"Pomyślnie włączono zapętlanie {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Zapętlanie zostało włączone.",
            )


def setup(bot: Smiffy):
    bot.add_cog(CommandLoop(bot))
