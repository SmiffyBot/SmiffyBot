from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Attachment, Color, Embed, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy

supported_colors: dict = {
    "Czerwony": Color.red(),
    "Niebieski": Color.blue(),
    "Żółty": Color.yellow(),
    "Fioletowy": Color.purple(),
    "Ciemny": Color.dark_theme(),
    "Zielony": Color.green(),
    "Pomarańczowy": Color.gold(),
}


class CommandEmbed(CustomCog):
    @slash_command(
        name="embed",
        description="Twórzy specjalny embed",
        dm_permission=False,
    )
    async def embed(
        self,
        interaction: CustomInteraction,
        title: str = SlashOption(
            name="tytuł",
            description="Podaj tytuł embedu",
            max_length=256,
        ),
        color: str = SlashOption(
            name="kolor",
            description="Wybierz kolor embedu",
            choices=supported_colors.keys(),
        ),
        description: str = SlashOption(
            name="opis",
            description="Podaj opis embedu",
            required=False,
            max_length=4000,
        ),
        image: Attachment = SlashOption(
            name="obraz",
            description="Podaj obraz embedu",
            required=False,
        ),
    ):
        embed = Embed(
            title=title,
            description=description,
            color=supported_colors[color],
        )
        if image:
            embed.set_thumbnail(url=image.url)

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandEmbed(bot))
