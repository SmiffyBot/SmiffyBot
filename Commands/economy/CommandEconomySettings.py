from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, SlashOption

from enums import Emojis
from typings import EconomyGuildSettings
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandEconomySettings(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="ustawienia", description="Ustaw ustawienia ekonomii na serwerze"
    )
    @PermissionHandler(manage_guild=True)
    async def economy_settings(
        self,
        interaction: CustomInteraction,
        start_money: Optional[int] = SlashOption(
            name="startowy_balans",
            description="Podaj startowy balans pieniędzy",
        ),
        max_money: Optional[int] = SlashOption(
            name="maksymalny_bilans",
            description="Podaj maksymalny balans jaki użytkownik może posiadać",
        ),
        work_win_rate: Optional[int] = SlashOption(
            name="praca_szansa_na_wygrana",
            description="Podaj szanse na wygrana od 1 do 100",
        ),
        work_cooldown: Optional[int] = SlashOption(
            name="częstotliwość_pracy",
            description="Podaj w sekundach co ile użytkownicy mogą pracować",
        ),
        work_max_income: Optional[int] = SlashOption(
            name="praca_maksymalny_przychod",
            description="Podaj maksymalną kwotę otrzymania pieniędzy za prace",
        ),
        work_min_income: Optional[int] = SlashOption(
            name="praca_minimalny_przychod",
            description="Podaj minimalną kwotę otrzymania pieniędzy za prace",
        ),
        coin_flip_cooldown: Optional[int] = SlashOption(
            name="częstotliwość_rzut_moneta",
            description="Podaj w sekundach co ile użytkownicy mogą używać rzut monetą",
        ),
    ):
        assert interaction.guild

        if not interaction.data:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        await interaction.response.defer()
        manager: EconomyManager = EconomyManager(bot=self.bot)

        if not await manager.get_guild_economy_status(interaction.guild):
            return await interaction.send_error_message(description="Ekonomia na serwerze jest wyłączona.")

        interaction_data: dict[str, list[dict]] = interaction.data["options"][0]  # pyright: ignore
        interaction_options: list[dict[str, int | str]] = interaction_data["options"]

        if len(interaction_options) == 0:
            return await interaction.send_error_message(description="Nie wybrałeś/aś żadnej opcji.")

        data_to_update: dict[str, int] = {}
        guild_data: EconomyGuildSettings = await manager.get_guild_settings(interaction.guild)
        embed_description: str = ""

        if start_money:
            if max_money and start_money > max_money:
                return await interaction.send_error_message(
                    description="Maksymalny balans nie może być niższy niż startowy balans."
                )
            if not max_money and start_money > guild_data["max_balance"]:
                return await interaction.send_error_message(
                    description="Maksymalny balans nie może być niższy niż startowy balans."
                )

            data_to_update["start_balance"] = abs(start_money)
            embed_description += f"> `💲` **Startowy balans:** `{abs(start_money)}$`\n\n"

        if max_money:
            if not start_money:
                if guild_data["start_balance"] > max_money:
                    return await interaction.send_error_message(
                        description="Maksymalny balans nie może być niższy niż startowy balans."
                    )
            if max_money <= 1:
                return await interaction.send_error_message(
                    description="Maksymalny balans nie może być niższy niż `1`"
                )

            if max_money > 100_000_000_000:
                return await interaction.send_error_message(
                    description="Maksymalny balans nie może być większy niż `100.000.000.000$`"
                )

            data_to_update["max_balance"] = abs(max_money)
            embed_description += f"> `〽️` **Maksymalny balans:** `{abs(max_money)}`\n\n"

        if work_win_rate:
            if work_win_rate > 100:
                return await interaction.send_error_message(
                    description="Szansa na zarobek pracy nie może być większa niż `100%`"
                )
            if work_win_rate <= 0:
                return await interaction.send_error_message(
                    description="Szansa na zarobek pracy nie może być niższa niż `1%`"
                )

            data_to_update["work_win_rate"] = work_win_rate
            embed_description += f"> `🔗` **Praca - szansa na wygraną:** `{work_win_rate}%`\n\n"

        if work_cooldown:
            if work_cooldown <= 0:
                return await interaction.send_error_message(
                    description="Częstotliwość pracy nie może być niższa niż `1s`"
                )
            if work_cooldown > 43200:
                return await interaction.send_error_message(
                    description="Częstotliwość pracy nie może być większa niż `43,200s`"
                )

            data_to_update["work_cooldown"] = work_cooldown
            embed_description += f"> `⚙️` **Praca - częstoliwość:** `{work_cooldown}s`\n\n"

        if work_max_income:
            if work_max_income <= 1:
                return await interaction.send_error_message(
                    description="Maksymalny przychód za pracę nie może być niższy niż `2$`"
                )
            if work_min_income and work_max_income <= work_min_income:
                return await interaction.send_error_message(
                    description="Minimalny przychód za pracę nie może być większy lub taki sam jak maksymalny."
                )
            if guild_data["work_min_income"] >= work_max_income:
                return await interaction.send_error_message(
                    description="Minimalny przychód za pracę nie może być większy lub taki sam jak maksymalny."
                )

            data_to_update["work_max_income"] = work_max_income
            embed_description += f"> `🍀` **Praca - maksymalny dochód:** `{work_max_income}$`\n\n"

        if work_min_income:
            if work_min_income <= 0:
                return await interaction.send_error_message(
                    description="Minimalny przychód za pracę nie może być niższy niż `1$`"
                )

            if not work_max_income:
                if guild_data["work_max_income"] <= work_min_income:
                    return await interaction.send_error_message(
                        description="Minimalny przychód za pracę nie może być większy lub taki sam jak maksymalny."
                    )
            else:
                if work_max_income <= work_min_income:
                    return await interaction.send_error_message(
                        description="Minimalny przychód za pracę nie może być większy lub taki sam jak maksymalny."
                    )

            data_to_update["work_min_income"] = work_min_income
            embed_description += f"> `☘️` **Praca - mininalny dochód:** `{work_min_income}$`\n\n"

        if coin_flip_cooldown:
            if coin_flip_cooldown <= 0:
                return await interaction.send_error_message(
                    description="Częstotliwość rzutem monetą nie może być niższe niż `0s`"
                )
            if coin_flip_cooldown > 43200:
                return await interaction.send_error_message(
                    description="Częstotliwość rzutem monetą nie może być większe niż `86400s`"
                )

            data_to_update["coin_flip_cooldown"] = coin_flip_cooldown
            embed_description += f"> `🎲` **Rzut monetą - częstotliwość:** `{coin_flip_cooldown}s`\n\n"

        await manager.update_guild_settings(interaction.guild, data_to_update)

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=embed_description,
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandEconomySettings(bot))
