from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Guild, Member, utils

from enums import Emojis
from typings import EconomyUserData
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandLeaderboard(CustomCog):
    async def get_leaderboard(
        self,
        guild: Guild,
        manager: EconomyManager,
        accounts: list[EconomyUserData],
    ) -> dict[Member, int]:
        total_money_lb: dict[Member, int] = {}

        for account in accounts:
            user_id: int = account["user_id"]
            member: Optional[Member] = await self.bot.cache.get_member(guild.id, user_id)
            if not member:
                await manager.delete_user_account(guild=guild, user_id=user_id)
                continue

            total_money: int = account["money"] + account["bank_money"]
            total_money_lb[member] = total_money

        sorted_lb: list[Member] = sorted(
            total_money_lb.items(),
            key=lambda item: item[1],  # pyright: ignore
            reverse=True,
        )
        return dict(sorted_lb)  # pyright: ignore

    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="topka",
        description="Top 10 osób w $.",
    )
    async def economy_leaderboard(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        accounts: list[EconomyUserData] = await manager.get_all_guild_accounts(interaction.guild)

        if not accounts:
            return await interaction.send_error_message(
                description="Na serwerze nie ma zarejestrowanych żadnych kont."
            )

        leaderboard: dict[Member, int] = await self.get_leaderboard(interaction.guild, manager, accounts)
        embed = Embed(
            title="`📈` Top 10 Ekonomia",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        index: int = 0
        for (
            member,
            total_money,
        ) in leaderboard.items():
            index += 1
            embed.add_field(
                name=f"`🔱` {index}. {member}",
                value=f"{Emojis.REPLY.value} `{total_money}$`",
                inline=False,
            )

            if index == 10:
                break

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandLeaderboard(bot))
