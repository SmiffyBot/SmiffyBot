from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from nextcord import File, Member, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandHorny(CustomCog):
    @slash_command(
        name="horny",
        description="Wysyła nakładke horny na avatar użytkownika",
        dm_permission=False,
    )
    async def horny(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj osobę",
        ),
    ):
        await interaction.response.defer()

        api_url: str = (
            f"https://some-random-api.com/canvas/horny?"
            f"avatar={interaction.avatars.get_user_avatar(member)}"
        )

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url=api_url,
            method="GET",
        )
        if not response:
            return

        data = BytesIO(await response.read())

        await interaction.send(file=File(data, "horny.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandHorny(bot))
