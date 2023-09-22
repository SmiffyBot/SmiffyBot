from __future__ import annotations

from typing import TYPE_CHECKING

from humanfriendly import InvalidTimespan, parse_timespan
from nextcord import SlashOption, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandSlowmode(CustomCog):
    @slash_command(  # pyright: ignore
        name="slowmode",
        description="Zmień prędkość wysyłania wiadomości na kanale.",
        dm_permission=False,
    )
    @PermissionHandler(
        manage_messages=True,
        user_role_has_permission="slowmode",
    )
    async def slowmode(
        self,
        interaction: CustomInteraction,
        time: str = SlashOption(
            name="prędkość",
            description="Wpisz prędkość np. 5m (5 minut).",
        ),
    ):
        try:
            seconds: int = int(parse_timespan(time))
        except InvalidTimespan:
            return await interaction.send_error_message(
                description="**Wpisałeś/aś niepoprawną jednostkę czasu.**\n> Przykład: `5s`, `5m`, `5h`"
            )
        if seconds > 21600:
            return await interaction.send_error_message(
                description="**Wpisałeś/aś zbyt duży czas. Maksymalny czas to `6` godzin**"
            )

        await interaction.response.defer()

        await interaction.channel.edit(slowmode_delay=seconds)  # pyright: ignore

        if "s" not in time and "m" not in time and "h" not in time:
            time = f"{time}s"

        await interaction.send_success_message(
            title=f"Zaktualizowano kanał {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Tryb powolny: `{time.lower()}`",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandSlowmode(bot))
