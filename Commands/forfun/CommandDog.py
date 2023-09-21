from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Embed, slash_command, utils

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import ClientResponse, Optional


class CommandDog(CustomCog):
    @slash_command(
        name="pies",
        description="Wysyła obrazek z randomowym pieskiem :)",
        dm_permission=False,
    )
    async def dog(self, interaction: CustomInteraction):
        await interaction.response.defer()

        response: Optional[ClientResponse] = await self.bot.session.send_api_request(
            interaction=interaction,
            url="https://some-random-api.com/animal/dog",
            method="GET",
        )

        if not response:
            return

        data = await response.json()

        embed = Embed(title="Oto Twój piesek.", timestamp=utils.utcnow(), color=Color.dark_theme())
        embed.set_image(url=data["image"])
        embed.set_footer(text=f"{interaction.user}", icon_url=interaction.user_avatar_url)
        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandDog(bot))
