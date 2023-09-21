from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import slash_command
from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy


class CommandHelp(CustomCog):

    @slash_command(name="pomoc", description="Komenda pomocy", dm_permission=False)
    async def help(self, interaction: CustomInteraction):
        ...


def setup(bot: Smiffy):
    bot.add_cog(CommandHelp(bot))

