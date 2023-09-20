from __future__ import annotations
from typing import TYPE_CHECKING

from mafic import errors
from nextcord import errors as nextcord_errors, Member
from utilities import CustomInteraction, CustomCog, PermissionHandler

from enums import Emojis
from .__main__ import MusicCog, MusicPlayer

if TYPE_CHECKING:
    from typings import PlayerT
    from bot import Smiffy


class CommandJoin(CustomCog):
    @MusicCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="dołącz", description="Dołącza na kanał głosowy"
    )
    @PermissionHandler(user_role_has_permission="music")
    async def music_join(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member) and interaction.guild

        await interaction.response.defer()

        if interaction.guild.owner_id != interaction.user.id:
            if interaction.guild.me.voice and interaction.guild.me.voice.channel:
                return await interaction.send_error_message(
                    description="Bot już jest aktualnie podłączony pod kanał głosowy.",
                )

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.send_error_message(
                description="Aby użyć tej funkcji musisz znajdować się na kanale głosowym.",
            )

        try:
            player: PlayerT = await interaction.user.voice.channel.connect(  # pyright: ignore
                cls=MusicPlayer  # pyright: ignore
            )
        except errors.NoNodesAvailable:
            return await interaction.send_error_message(
                description="Bot nie ma do dyspozycji żadnych wolnych wątków. Spróbuj ponownie później.",
            )
        except nextcord_errors.ClientException:
            await interaction.guild.me.disconnect()

            player: PlayerT = await interaction.user.voice.channel.connect(  # pyright: ignore
                cls=MusicPlayer  # pyright: ignore
            )

        await interaction.guild.change_voice_state(
            channel=interaction.guild.me.voice.channel,  # pyright: ignore
            self_deaf=True,
        )

        player.channel_last_command = interaction.channel  # pyright: ignore

        await interaction.send_success_message(
            title=f"Pomyślnie dołączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Dołączyłem na kanał: {interaction.user.voice.channel.mention}",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandJoin(bot))
