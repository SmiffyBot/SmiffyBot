from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO
from nextcord import slash_command, SlashOption, File, Member
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandAdios(CustomCog):
    @slash_command(
        name="adios",
        description="Wysyła nakładke adios z avatarem wybranej osoby.",
        dm_permission=False,
    )
    async def adios(
        self,
        interaction: CustomInteraction,
        user: Member = SlashOption(
            name="osoba",
            description="Podaj osobę",
        ),
    ):
        await interaction.response.defer()

        api_url: str = f"https://vacefron.nl/api/adios?user={user.display_avatar.url}"

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )

        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "adios.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandAdios(bot))
