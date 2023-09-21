from __future__ import annotations

from random import randint
from typing import TYPE_CHECKING

from nextcord import Color, Embed, Member, SlashOption, slash_command

from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy


class CommandShip(CustomCog):
    @slash_command(
        name="ship",
        description="Wskaznik shipu w %",
        dm_permission=False,
    )
    async def ship(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Podaj pierwszą osobę",
        ),
        second_member: Member = SlashOption(
            name="druga_osoba",
            description="Podaj drugą osobe",
        ),
    ):
        await interaction.response.defer()

        percent = randint(0, 100)
        embed = Embed(
            title="Wynik shipu",
            color=Color(0xEB4034),
            description=f"{member.mention} :revolving_hearts: :revolving_hearts: {second_member.mention}"
            f"\n> **Wynik:** `{percent}%`",
        )

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandShip(bot))
