from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Member
from utilities import CustomInteraction, CustomCog, PermissionHandler

from enums import Emojis
from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from typings import PlayerT
    from bot import Smiffy


class CommandPause(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="pauza", description="Pauzuje aktualną piosenke"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_pause(self, interaction: CustomInteraction):
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

        if player.paused:
            return await interaction.send_error_message(description="Muzyka już jest zatrzymana.")

        await player.pause()

        resume_command: str = interaction.get_command_mention(command_name="muzyka", sub_command="wznów")

        await interaction.send_success_message(
            title=f"Pomyślnie włączono pauze {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Aktualna piosenka została zatrzymana.\n"
            f"Użyj {resume_command}, aby wznowić.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandPause(bot))
