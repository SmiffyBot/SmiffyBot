from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from nextcord import File, Member, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandRespect(CustomCog):
    @slash_command(
        name="respekt",
        description="Wysyła nakładke respektu na avatar użytkownika",
        dm_permission=False,
    )
    async def respect(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę"),
    ):
        await interaction.response.defer()

        api_url: str = (
            f"https://some-random-api.com/canvas/passed?avatar={interaction.avatars.get_user_avatar(member)}"
        )

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )

        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "respect.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandRespect(bot))
