from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy


class CommandPing(CustomCog):
    @slash_command(
        name="ping",
        description="Sprawdź aktualne opóźnienie bota!",
        dm_permission=False,
    )
    async def ping(self, interaction: CustomInteraction):
        (
            latency,
            shard,
        ) = interaction.get_bot_latency(interaction.guild)

        await interaction.send("> Ping! :ping_pong:")
        await interaction.edit_original_message(
            content=f"***Pong*** `{latency}ms` :ping_pong:" f"\n***Shard:*** `{shard}`"
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandPing(bot))
