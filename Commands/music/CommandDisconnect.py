from __future__ import annotations

from typing import TYPE_CHECKING

from mafic import errors
from nextcord import Member

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import MusicCog

if TYPE_CHECKING:
    from nextcord import VoiceChannel

    from bot import Smiffy


class CommandDisconnect(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="odłącz",
        description="Wychodzi z kanału głosowego.",
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_disconnect(self, interaction: CustomInteraction):
        assert interaction.guild and isinstance(interaction.user, Member)

        await interaction.response.defer()

        if not interaction.guild.me.voice or not interaction.guild.me.voice.channel:
            return await interaction.send_error_message(
                description="Bot nie jest podłączony pod żaden kanał.",
            )

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
            )

        if interaction.user.voice.channel.id != interaction.guild.me.voice.channel.id:
            return await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na tym samym kanale głosowym co bot.",
            )

        try:
            channel: VoiceChannel = interaction.guild.me.voice.channel  # pyright: ignore
            await interaction.guild.me.disconnect()
        except errors.NoNodesAvailable:
            return await interaction.send_error_message(
                description="Bot nie ma do dyspozycji żadnych wolnych wątków.",
            )

        await interaction.send_success_message(
            title=f"Pomyślnie odłączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Odłączono z kanału: {channel.mention}",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandDisconnect(bot))
