from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, SlashOption, TextChannel, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandLogs(CustomCog):
    @slash_command(name="logi", dm_permission=False)
    async def logs(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @logs.subcommand(
        name="włącz",
        description="Włącza logi na serwerze.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def logs_on(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanal",
            description="Podaj kanał na którym mają przychodzić logi.",
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM server_logs WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if response:
            await self.bot.db.execute_fetchone(
                "UPDATE server_logs SET channel_id = ? WHERE guild_id = ?",
                (
                    channel.id,
                    interaction.guild.id,
                ),
            )
        else:
            await self.bot.db.execute_fetchone(
                "INSERT INTO server_logs(guild_id, channel_id) VALUES(?,?)",
                (
                    interaction.guild.id,
                    channel.id,
                ),
            )

        return await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Kanał: {channel.mention} został ustawiony jako logi serwera.",
            color=Color.green(),
        )

    @logs.subcommand(
        name="wyłącz",
        description="Wyłącza logi na serwerze.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def logs_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM server_logs WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            return await interaction.send_error_message(description="Logi na serwerze już są wyłączone.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM server_logs WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Wyłączono logi na serwerze.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandLogs(bot))
