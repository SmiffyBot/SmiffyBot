from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import Embed, Color, utils, slash_command, ui, SelectOption

from utilities import CustomInteraction, CustomCog, PermissionHandler
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class PunishmentSelect(ui.Select):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label="Ban",
                description="Użytkownik zostanie zbanowany permametnie po wysłaniu linku.",
                emoji="⛔",
            ),
            SelectOption(
                label="Kick",
                description="Użytkownik zostanie wyrzucony z serwera po wysłaniu linku.",
                emoji="👋",
            ),
            SelectOption(
                label="Warn",
                description="Użytkownik otrzyma ostrzeżenie po wysłaniu linku.",
                emoji="📌",
            ),
            SelectOption(
                label="Brak",
                description="Użytkownik nie otrzyma żadnej kary.",
                emoji="🧷",
            ),
        ]

        super().__init__(placeholder="Wybierz karę.", options=options)

    async def callback(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        await interaction.response.defer()

        punishment: str = self.values[0]
        bot: Smiffy = interaction.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM antylink WHERE guild_id = ?", (interaction.guild.id,)
        )
        if response:
            await interaction.send_error_message(description="Antylink już jest włączony.")
            return

        await bot.db.execute_fetchone(
            "INSERT INTO antylink(guild_id, punishment) VALUES(?,?)",
            (interaction.guild.id, punishment.lower()),
        )

        await interaction.send_success_message(
            title=f"Zaktualizowano Antylink {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Antylink został pomyślnie włączony.",
            color=Color.green(),
        )


class PunishmentSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(PunishmentSelect())


class CommandAntylink(CustomCog):
    @slash_command(name="antylink", dm_permission=False)
    async def antylink(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @antylink.subcommand(name="włącz", description="Włącza system Antylink")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def antylink_on(self, interaction: CustomInteraction):
        embed = Embed(
            title="`📃` Wybierz z listy karę",
            color=Color.yellow(),
            description=f"{Emojis.REPLY.value} Wybrana przez ciebie kara zostane nadana po wysłaniu linku.",
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        punishmentlistview = PunishmentSelectView()
        await interaction.send(embed=embed, ephemeral=True, view=punishmentlistview)

    @antylink.subcommand(name="wyłącz", description="Wyłącza system Antylink")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def antylink_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM antylink WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not response:
            return await interaction.send_error_message(description="Antylink już jest wyłączony.")

        await self.bot.db.execute_fetchone("DELETE FROM antylink WHERE guild_id = ?", (interaction.guild.id,))
        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Antylink został pomyślnie wyłączony.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandAntylink(bot))
