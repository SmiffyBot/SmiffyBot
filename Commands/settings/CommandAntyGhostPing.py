from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandAntyGhostPing(CustomCog):
    @slash_command(name="antyghostping", dm_permission=False)
    async def antyghostping(self, interaction: CustomInteraction):
        pass

    @antyghostping.subcommand(
        name="włącz",
        description="Włącza AntyGhostPing na serwerze",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def antyghostping_on(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM antyghostping WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if response:
            return await interaction.send_error_message(description="AntyGhostPing już jest włączony.")

        await self.bot.db.execute_fetchone(
            "INSERT INTO antyghostping(guild_id) VALUES(?)",
            (interaction.guild.id,),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie włączono AntyGhostPing {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} System AntyGhostPing został włączony.",
            color=Color.green(),
        )

    @antyghostping.subcommand(  # pyright: ignore
        name="wyłącz",
        description="Wyłącza AntyGhostPing na serwerze",
    )
    @PermissionHandler(manage_guild=True)
    async def antyghostping_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM antyghostping WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(description="AntyGhostPing już jest wyłączony.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM antyghostping WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono AntyGhostPing {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} System AntyGhostPing został wyłączony.",
            color=Color.green(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandAntyGhostPing(bot))
