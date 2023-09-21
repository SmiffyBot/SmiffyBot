from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from nextcord import File, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandAchievement(CustomCog):
    @slash_command(
        name="osiągnięcie",
        description="Wysyła nakładke osiągnięcia z gry minecraft",
        dm_permission=False,
    )
    async def achievement(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(name="tekst", description="Podaj treść osiągnięcia.", max_length=32),
    ):
        await interaction.response.defer()

        api_url: str = f"https://api.alexflipnote.dev/achievement?text={text}&icon=1"

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )

        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "mc.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandAchievement(bot))
