from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import SlashOption, TextChannel, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandLock(CustomCog):
    @slash_command(
        name="zablokujkanal", description="Blokuje wybrany kanał", dm_permission=False
    )  # pyright: ignore
    @PermissionHandler(manage_channels=True)
    async def lock(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanał",
            description="Podaj kanał który chcesz zablokować",
            required=False,
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()

        if not channel:
            channel = interaction.channel  # pyright: ignore

        await channel.set_permissions(interaction.guild.default_role, send_messages=False)

        unlock_command_mention: str = interaction.get_command_mention(command_name="odblokujkanal")

        await interaction.send_success_message(
            title=f"Pomyślnie zablokowano kanał {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Odblokuj go używając {unlock_command_mention}",
        )

    @slash_command(
        name="odblokujkanal",
        description="Odblokowuje wybrany kanał",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(manage_channels=True)
    async def unlock(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanał",
            description="Podaj kanał który chcesz odblokować",
            required=False,
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()

        if not channel:
            channel = interaction.channel  # pyright: ignore

        await channel.set_permissions(interaction.guild.default_role, send_messages=True)

        await interaction.send_success_message(
            title=f"Pomyślnie odblokowano kanał {Emojis.GREENBUTTON.value}"
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandLock(bot))
