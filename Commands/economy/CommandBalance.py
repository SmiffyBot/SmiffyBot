from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Member, SlashOption

from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandBalance(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="stan_konta",
        description="Wyświetla stan konta osoby.",
    )
    async def economy_balance(
        self,
        interaction: CustomInteraction,
        user: Optional[Member] = SlashOption(
            name="osoba",
            description="Podaj osobę której chcesz sprawdzić balans",
        ),
    ):
        await interaction.response.defer()
        member = user or interaction.user

        assert isinstance(member, Member) and interaction.guild

        if member.bot:
            return await interaction.send_error_message(description="Boty nie posiadają kont bankowych.")

        assert isinstance(member, Member)

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        (
            money,
            bank_money,
        ) = await manager.get_user_balance(member)

        await interaction.send_success_message(
            title=f"`💸` Stan konta {member}",
            description=f"- Portfel: `{money}$`\n- Bank: `{bank_money}$`",
            color=Color.dark_theme(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandBalance(bot))
