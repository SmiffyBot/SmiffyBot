from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from nextcord import File, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandAlert(CustomCog):
    @slash_command(
        name="alert",
        description="Tworzy obrazek z alertem",
        dm_permission=False,
    )
    async def alert(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(
            name="tekst",
            description="Podaj tekst alertu",
            max_length=80,
        ),
    ):
        await interaction.response.defer()

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url=f"https://api.popcat.xyz/alert?text={text}",
            method="GET",
        )
        if not response:
            return

        data = BytesIO(await response.read())

        await interaction.send(file=File(data, "alert.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandAlert(bot))
