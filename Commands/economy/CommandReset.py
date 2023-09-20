from __future__ import annotations
from typing import TYPE_CHECKING

from nextcord import Color, ui, ButtonStyle, Embed, utils

from utilities import CustomInteraction, CustomCog, PermissionHandler
from enums import Emojis

from .__main__ import EconomyCog

if TYPE_CHECKING:
    from bot import Smiffy


class ConfirmReset(ui.View):
    def __init__(self, interaction: CustomInteraction, bot: Smiffy):
        super().__init__(timeout=None)

        self.bot: Smiffy = bot
        self.original_interaction: CustomInteraction = interaction
        self.tables: tuple[str, ...] = (
            "economy_settings",
            "economy_shop",
            "economy_users",
        )

    async def interaction_check(self, interaction: CustomInteraction):
        assert interaction.user and self.original_interaction.user

        if interaction.user.id == self.original_interaction.user.id:
            return True

        return await interaction.send_error_message("Nie możesz tego użyć.", ephemeral=True)

    @ui.button(  # pyright: ignore
        label="Anuluj",
        style=ButtonStyle.red,
        emoji="<:suggestiondislike:997650135209222344>",
    )
    async def cancel(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        await self.original_interaction.delete_original_message()

    @ui.button(  # pyright: ignore
        label="Potwierdź",
        style=ButtonStyle.green,
        emoji="<:suggestionlike:997650032683667506>",
    )
    async def confirm(
        self, button: ui.Button, interaction: CustomInteraction
    ):  # pylint: disable=unused-argument
        assert interaction.guild

        await self.original_interaction.delete_original_message()

        embed = Embed(
            title="Resetowanie ekonomii <a:loading:919653287383404586>",
            color=Color.red(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        await interaction.send_success_message(
            title="Resetowanie ekonomii <a:loading:919653287383404586>",
            color=Color.red(),
            description=f"{Emojis.REPLY.value} Trwa resetowanie ekonomii na serwerze.",
        )

        for tabel in self.tables:
            await self.bot.db.execute_fetchone(
                f"DELETE FROM {tabel} WHERE guild_id = ?", (interaction.guild.id,)
            )

        embed = Embed(
            title=f"Pomyślnie zresetowano ekonomię {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Ekonomia na serwerze została zresetowana.",
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        await interaction.edit_original_message(embed=embed)


class CommandReset(CustomCog):
    @EconomyCog.main.subcommand(  # pylint: disable=no-member  # pyright: ignore
        name="reset", description="Resetuję całą ekonomie na serwerze"
    )
    @PermissionHandler(manage_guild=True)
    async def economy_reset(self, interaction: CustomInteraction):
        embed = Embed(
            title="`🛠️` Potwierdź resetowanie ekonomii",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Reset ekonomii obejmuje sklep, użytkowników, ustawień.",
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        buttons = ConfirmReset(interaction, self.bot)
        await interaction.send(embed=embed, view=buttons)


def setup(bot: Smiffy):
    bot.add_cog(CommandReset(bot))
