from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Embed, Color, utils, slash_command
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandMeme(CustomCog):
    @slash_command(name="mem", description="Wysyła randomowego mema.", dm_permission=False)
    async def meme(self, interaction: CustomInteraction):
        await interaction.response.defer()

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction, url="https://ivall.pl/memy", method="GET"
        )

        if not response:
            return

        meme_data: dict = await response.json()
        meme_link = meme_data["url"]
        embed = Embed(title="Oto twój mem!", color=Color.blue(), timestamp=utils.utcnow())
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_image(url=meme_link)

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandMeme(bot))
