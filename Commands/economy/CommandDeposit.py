from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Member, SlashOption, Color
from utilities import CustomInteraction, CustomCog
from enums import Emojis

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandDeposit(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="wpłać", description="Wpłaca pieniądze do banku"
    )
    async def economy_deposit(
        self,
        interaction: CustomInteraction,
        amount: int = SlashOption(name="kwota", description="Podaj kwotę do wpłacenia"),
    ):
        await interaction.response.defer()

        assert isinstance(interaction.user, Member) and interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        money, bank_money = await manager.get_user_balance(user=interaction.user)

        if amount > money:
            return await interaction.send_error_message(
                description="Nie posiadasz tylu pieniędzy w portfelu."
            )

        await manager.update_user_account(
            interaction.user,
            {"money": money - amount, "bank_money": bank_money + amount},
        )

        await interaction.send_success_message(
            title=f"Pomyślnie wpłacono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Wpłacono: `{amount}$` na twoje konto bankowe.",
            color=Color.dark_theme(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandDeposit(bot))
