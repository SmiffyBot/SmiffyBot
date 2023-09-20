from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO
from nextcord import slash_command, SlashOption, File
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandComment(CustomCog):
    @slash_command(
        name="komentarz",
        description="Wysyła fałszywy obrazek twojego komentarza na youtubie",
        dm_permission=False,
    )
    async def comment(
        self,
        interaction: CustomInteraction,
        title: str = SlashOption(name="treść", description="Podaj treść komentarza"),
    ):
        assert interaction.user

        await interaction.response.defer()
        api_url: str = (
            f"https://some-random-api.com/canvas/youtube-comment?username={interaction.user.display_name}"
            f"&&comment={title}&&avatar={interaction.user_avatar_url}"
        )

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )

        if not response:
            return
        data = BytesIO(await response.read())

        await interaction.send(file=File(data, "comment.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandComment(bot))
