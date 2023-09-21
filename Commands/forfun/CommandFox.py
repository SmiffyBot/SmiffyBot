from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, slash_command, utils

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandFox(CustomCog):
    @slash_command(
        name="lis",
        description="Wysyła obrazek z randomowym lisem :)",
        dm_permission=False,
    )
    async def fox(self, interaction: CustomInteraction):
        await interaction.response.defer()

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url="https://some-random-api.com/img/fox",
            method="GET",
        )
        if not response:
            return

        data: dict = await response.json()

        embed = Embed(title="Oto Twój liseł.", timestamp=utils.utcnow(), color=Color.dark_theme())
        embed.set_image(url=data["link"])
        embed.set_footer(text=f"{interaction.user}", icon_url=interaction.user_avatar_url)
        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandFox(bot))
