from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import SlashOption

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

from .__main__ import EconomyCog, EconomyManager

if TYPE_CHECKING:
    from bot import Smiffy


class CommandStatus(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="status",
        description="Włącz lub wyłącz ekonomie na serwerze.",
    )
    @PermissionHandler(manage_guild=True)
    async def economy_status(
        self,
        interaction: CustomInteraction,
        status: str = SlashOption(
            name="status",
            description="Wybierz status ekonomii",
            choices={
                "Włącz": "on",
                "Wyłącz": "off",
            },
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()

        manager: EconomyManager = EconomyManager(bot=self.bot)
        economy_guild_status: bool = await manager.get_guild_economy_status(interaction.guild)

        if status == "on":
            if economy_guild_status:
                return await interaction.send_error_message(description="Ekonomia już jest włączona.")
            await manager.set_guild_economy_status(interaction.guild, True)
            return await interaction.send_success_message(
                title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Włączono ekonomie na serwerze.",
            )

        if not economy_guild_status:
            return await interaction.send_error_message(description="Ekonomia już jest wyłączona")

        await manager.set_guild_economy_status(interaction.guild, False)
        return await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Wyłączono ekonomie na serwerze.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandStatus(bot))
