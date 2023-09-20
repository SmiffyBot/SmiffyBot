from __future__ import annotations
from typing import TYPE_CHECKING

from io import BytesIO
from nextcord import slash_command, SlashOption, File
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandTweet(CustomCog):
    @slash_command(
        name="tweet",
        description="Wysyła fałszywy obrazek z twojego tweeta na twitterze",
        dm_permission=False,
    )
    async def tweet(
        self,
        interaction: CustomInteraction,
        title: str = SlashOption(name="treść", description="Podaj treść tweeta"),
    ):
        assert interaction.user

        await interaction.response.defer()

        api_url: str = (
            f"https://some-random-api.com/canvas/tweet?avatar={interaction.user_avatar_url}"
            f"&&comment={title}&&displayname={interaction.user.display_name}&&username={interaction.user}"
        )

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url=api_url, method="GET"
        )

        if not response:
            return

        data: BytesIO = BytesIO(await response.read())

        await interaction.send(file=File(data, "tweet.png"))


def setup(bot: Smiffy):
    bot.add_cog(CommandTweet(bot))
