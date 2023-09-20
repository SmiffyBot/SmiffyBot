from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Member
from enums import Emojis
from utilities import CustomInteraction, CustomCog, PermissionHandler

from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import PlayerT


class CommandResume(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="wznów", description="Wyłącza pauze z piosenki"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_resume(self, interaction: CustomInteraction):
        assert interaction.guild and isinstance(interaction.user, Member)

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

        if not player.paused:
            return await interaction.send_error_message(description="Muzyka nie jest zatrzymana.")

        await player.resume()

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono pauze {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Aktualna piosenka została wznowiona.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandResume(bot))
