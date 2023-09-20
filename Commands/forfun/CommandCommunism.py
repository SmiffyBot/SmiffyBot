from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO
from nextcord import slash_command, Member, SlashOption, File
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandCommunism(CustomCog):
    @slash_command(
        name="komunizm",
        description="Konwertuje avatar wybranej osoby",
        dm_permission=False,
    )
    async def communism(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(name="osoba", description="Wybierz osobę"),
    ):
        await interaction.response.defer()

        api_url: str = (
            f"https://some-random-api.com/canvas/overlay/comrade?"
            f"avatar={interaction.avatars.get_user_avatar(member)}"
        )

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )
        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "communism.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandCommunism(bot))
