from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from nextcord import Color, slash_command, SlashOption, TextChannel

from utilities import CustomInteraction, CustomCog, PermissionHandler
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandSuggestions(CustomCog):
    @slash_command(name="propozycje", dm_permission=False)
    async def suggestions(
        self, interaction: CustomInteraction, dm_permission=False
    ):  # pylint: disable=unused-argument
        ...

    @suggestions.subcommand(name="włącz", description="Włącza propozycjne na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def suggestions_on(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanał", description="Podaj kanał na którym mają być propozycje"
        ),
        comments: str = SlashOption(
            name="komentarze",
            description="Włącz lub wyłącz komentarze pod propozycjami",
            choices={"Włącz": "on", "Wyłącz": "off"},
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM suggestions WHERE guild_id = ?", (interaction.guild.id,)
        )

        if response:
            return await interaction.send_error_message(description="Propozycje już są włączone.")

        await self.bot.db.execute_fetchone(
            "INSERT INTO suggestions(guild_id, channel_id, comments) VALUES(?,?,?)",
            (interaction.guild.id, channel.id, comments),
        )
        return await interaction.send_success_message(
            title=f"Pomyślnie włączono propozycje {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Kanał: {channel.mention}",
        )

    @suggestions.subcommand(name="wyłącz", description="Wyłącz propozycje na serwerze")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def suggestions_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM suggestions WHERE guild_id = ?", (interaction.guild.id,)
        )
        if not response:
            return await interaction.send_error_message(description="Propozycje już są wyłączone.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM suggestions WHERE guild_id = ?", (interaction.guild.id,)
        )
        return await interaction.send_success_message(
            title=f"Pomyślnie wyłączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Propozycje zostały wyłączone.",
            color=Color.green(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandSuggestions(bot))
