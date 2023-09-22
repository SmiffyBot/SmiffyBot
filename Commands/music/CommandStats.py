from __future__ import annotations

from typing import TYPE_CHECKING

from mafic import __version__  # pylint: disable=ungrouped-imports
from nextcord import Color, Embed, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction, Optional

from .__main__ import MusicCog

if TYPE_CHECKING:
    from mafic import Node, NodeStats

    from bot import Smiffy


class CommandStats(CustomCog):
    @staticmethod
    def bytesto(_bytes: int, to: str, bsize=1024):
        a = {
            "k": 1,
            "m": 2,
            "g": 3,
            "t": 4,
            "p": 5,
            "e": 6,
        }
        float(_bytes)
        return _bytes / (bsize ** a[to])

    @MusicCog.main.subcommand(  # pylint: disable=no-member
        name="statystyki",
        description="Statystyki muzyki Smiffiego.",
    )
    async def music_stats(self, interaction: CustomInteraction):
        await interaction.response.defer()

        try:
            node: Node = self.bot.pool.label_to_node["Smiffy-Europe"]
        except KeyError:
            return await interaction.send_error_message(
                description="Wygląda na to, że bot się jeszcze w pełni nie uruchomił.",
            )

        node_stats: Optional[NodeStats] = node.stats
        if not node_stats:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        cpu_cores: int = node_stats.cpu.cores
        cpu_usage: float = round(node_stats.cpu.lavalink_load, 6)

        memory_used: int = int(self.bytesto(node_stats.memory.used, "m"))
        memory_allocated: int = int(self.bytesto(node_stats.memory.allocated, "m"))
        players: int = node_stats.player_count

        embed = Embed(
            title="`📈` Statystyki Muzyki",
            colour=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.add_field(
            name="`〽️` Zużycie Cpu",
            value=f"{Emojis.REPLY.value} `{cpu_usage}%`",
        )

        embed.add_field(
            name="`🔎` Zużycie Ramu",
            value=f"{Emojis.REPLY.value} `{memory_used}MB`/`{memory_allocated}MB`",
            inline=False,
        )

        embed.add_field(
            name="`🔧` Wątki",
            value=f"{Emojis.REPLY.value} `{cpu_cores}`",
            inline=False,
        )

        embed.add_field(
            name="`📌` Aktywne playery",
            value=f"{Emojis.REPLY.value} `{players}`",
        )

        embed.set_footer(text=f"Mafic: v{__version__} | Lavalink: v4.0")

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandStats(bot))
