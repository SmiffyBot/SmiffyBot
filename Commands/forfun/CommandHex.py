from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from nextcord import File, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandHex(CustomCog):
    @slash_command(name="hex", description="Pokazuje wpisany kolor hex", dm_permission=False)
    async def hex(
        self,
        interaction: CustomInteraction,
        color_hex: str = SlashOption(
            name="hex",
            description="Wpisz kolor w formacie hex",
            min_length=6,
            max_length=7,
        ),
    ):
        await interaction.response.defer()

        api_url: str = f"https://some-random-api.com/canvas/misc/colorviewer?hex={color_hex.replace('#', '')}"

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )
        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "hex.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandHex(bot))
