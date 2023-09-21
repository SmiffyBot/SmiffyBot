from __future__ import annotations

from random import choice
from typing import TYPE_CHECKING

from nextcord import Color, Embed, SlashOption, slash_command, utils

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy


class CommandQuestion(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot=bot)

        self.answers: tuple[str, ...] = (
            "Tak",
            "Nie",
            "Możliwe",
            "Raczej tak",
            "Raczej nie",
        )

    @slash_command(
        name="pytanie",
        description="Zadaj pytanie, a bot odpowie tak lub nie.",
        dm_permission=False,
    )
    async def question(
        self,
        interaction: CustomInteraction,
        question: str = SlashOption(name="treść", description="Wpisz treść pytania."),
    ):
        embed = Embed(
            title="Odpowiedź na pytanie",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"Pytanie: **{question}**\n> Odpowiedź: **{choice(self.answers)}**",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandQuestion(bot))
