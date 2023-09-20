from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO
from nextcord import slash_command, SlashOption, File, Member
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandTriggered(CustomCog):
    @slash_command(
        name="triggered",
        description="Wysyła nakładke triggered na avatar użytkownika",
        dm_permission=False,
    )
    async def triggered(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Podaj osobę"),
    ):
        await interaction.response.defer()

        api_url = f"https://some-random-api.com/canvas/triggered?avatar={interaction.avatars.get_user_avatar(member)}"

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )

        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "triggered.gif"))


def setup(bot: Smiffy):
    bot.add_cog(CommandTriggered(bot))
