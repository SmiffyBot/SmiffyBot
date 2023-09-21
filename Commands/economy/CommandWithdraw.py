from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Color, Member, SlashOption

from enums import Emojis
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandWitdraw(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="wypłać", description="Wypłaca pieniądze z banku do portfela"
    )
    async def economy_withdraw(
        self,
        interaction: CustomInteraction,
        amount: int = SlashOption(name="kwota", description="Podaj kwotę do wypłacenia"),
    ):
        await interaction.response.defer()
        assert isinstance(interaction.user, Member) and interaction.guild

        manager: EconomyManager = EconomyManager(bot=self.bot)
        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        money, bank_money = await manager.get_user_balance(user=interaction.user)

        if amount > bank_money:
            return await interaction.send_error_message(description="Nie posiadasz tylu pieniędzy w banku.")

        await manager.update_user_account(
            interaction.user,
            {"money": money + amount, "bank_money": bank_money - amount},
        )

        await interaction.send_success_message(
            title=f"Pomyślnie wypłacono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Wypłacono: `{amount}$` do twojego portfela.",
            color=Color.dark_theme(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandWitdraw(bot))
