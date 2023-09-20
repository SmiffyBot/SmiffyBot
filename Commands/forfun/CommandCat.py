from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Embed, Color, utils, slash_command
from utilities import CustomInteraction, CustomCog

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandCat(CustomCog):
    @slash_command(name="kot", description="Wysyła randomowy obrazek kici.", dm_permission=False)
    async def cat(self, interaction: CustomInteraction):
        await interaction.response.defer()

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url="https://some-random-api.com/animal/cat",
            method="GET",
        )
        if not response:
            return

        data = await response.json()

        embed = Embed(title="Oto Twój kitku.", color=Color.dark_theme(), timestamp=utils.utcnow())
        embed.set_footer(text=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_image(url=data["image"])

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandCat(bot))
