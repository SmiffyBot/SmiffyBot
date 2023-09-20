from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import slash_command, SlashOption
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy


class CommandSay(CustomCog):
    @slash_command(
        name="powiedz",
        description="Bot powie wszystko, co rozkażesz.",
        dm_permission=False,
    )
    async def say(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(name="tekst", description="Wpisz tekst"),
    ):
        await interaction.send(text)


def setup(bot: Smiffy):
    bot.add_cog(CommandSay(bot))
