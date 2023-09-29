from __future__ import annotations

from random import randint
from typing import TYPE_CHECKING, Optional

from cooldowns import CallableOnCooldown, shared_cooldown
from nextcord import Color, Member

from enums import Emojis
from typings import DB_RESPONSE, EconomyGuildSettings
from utilities import CustomCog, CustomInteraction

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandWork(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member
        name="pracuj",
        description="Pracuj i zdobywaj pieniądze.",
    )
    @shared_cooldown("command_work")
    async def economy_work(self, interaction: CustomInteraction):
        assert interaction.guild

        await interaction.response.defer()
        assert isinstance(interaction.user, Member)

        manager: EconomyManager = EconomyManager(bot=self.bot)
        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        guild_settings: EconomyGuildSettings = await manager.get_guild_settings(interaction.guild)

        work_win_rate: int = guild_settings["work_win_rate"]
        work_min_income: int = guild_settings["work_min_income"]
        work_max_income: int = guild_settings["work_max_income"]

        income: int = randint(work_min_income, work_max_income)

        if randint(1, 100) > work_win_rate:
            income: int = int(income / 2)
            await manager.remove_user_money(interaction.user, income)

            return await interaction.send_success_message(
                title="`💸` Straciłeś pieniądze.",
                color=Color.red(),
                description=f"{Emojis.REPLY.value} Niestety, ale właśnie straciłeś/aś: `{income}$`",
            )

        await manager.add_user_money(
            interaction.user,
            money_data={"money": income},
        )
        await interaction.send_success_message(
            title="`💸` Otrzymano wypłatę.",
            description=f"{Emojis.REPLY.value} Właśnie otrzymałeś/aś wypłatę w wysokości: `{income}$`",
            color=Color.green(),
        )

    @economy_work.error  # pyright: ignore
    async def economy_work_error(
        self,
        interaction: CustomInteraction,
        error,
    ):
        assert interaction.guild

        error = getattr(error, "original", error)

        if isinstance(error, CallableOnCooldown):
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "SELECT work_cooldown FROM economy_settings WHERE guild_id = ?",
                (interaction.guild.id,),
            )

            if not response or not response[0]:
                return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

            waited_seconds: Optional[int] = await EconomyManager.get_waited_seconds(interaction, "command_work")

            if not waited_seconds:
                return await interaction.send_error_message(
                    description="Wystąpił nieoczekiwany błąd. Spróbuj użyć komendy ponownie."
                )

            cooldown_seconds: int = response[0]

            remaining_seconds: int = int(cooldown_seconds - waited_seconds)

            await interaction.send_error_message(
                description=f"Tej komendy możesz użyć dopiero za: `{remaining_seconds}s`"
            )


def setup(bot: Smiffy):
    bot.add_cog(CommandWork(bot))
