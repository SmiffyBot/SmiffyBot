from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from nextcord import File, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandDidYouMean(CustomCog):
    @slash_command(
        name="didyoumean",
        description="Wysyła nakładkę did you mean z podanym tekstem",
        dm_permission=False,
    )
    async def didyoumean(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(
            name="tekst",
            description="Podaj treść nakładki",
            max_length=32,
        ),
        second_text: str = SlashOption(
            name="drugi_tekst",
            description="Podaj drugą treść nakładki",
            max_length=32,
        ),
    ):
        text, second_text = text.replace("&", ""), second_text.replace("&", "")

        await interaction.response.defer()

        api_url: str = f"https://api.alexflipnote.dev/didyoumean?top={text}&bottom={second_text}"

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url=api_url,
            method="GET",
        )

        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "didyoumean.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandDidYouMean(bot))
