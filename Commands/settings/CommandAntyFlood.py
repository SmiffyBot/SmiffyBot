from __future__ import annotations

from asyncio import exceptions
from typing import TYPE_CHECKING, Optional

from nextcord import Color, Embed, Message, slash_command, utils

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandAntyFlood(CustomCog):
    @slash_command(name="antyflood", dm_permission=False)
    async def antyflood(self, interaction: CustomInteraction):  # pylint: disable=unused-argument
        ...

    @antyflood.subcommand(name="włącz", description="Włącza system AntyFlood")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def antyflood_on(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM antyflood WHERE guild_id = ?", (interaction.guild.id,)
        )

        if response:
            return await interaction.send_error_message(description="AntyFlood już jest włączony.")

        embed = Embed(
            title="`🛠️` Konfigurowanie AntyFlood.",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Podaj ilość takich samych wiadomości w ciągu 5 minut, "
            f"po których bot ma zacząć usuwać wiadomości.\n- **Zalecane:** `3`",
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_footer(text="Etap 1/1")

        await interaction.send(embed=embed)

        try:
            limit_message: Message = await self.bot.wait_for(
                "message",
                check=lambda message: message.author == interaction.user,
                timeout=12,
            )
            await limit_message.delete()

        except exceptions.TimeoutError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} *Konfiguracja przerwana (Upłynął limit czasu).\n\n"
                f"Wiadomość zostanie usunięta automatycznie za* **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer()
            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        try:
            message_limit: int = abs(int(limit_message.content))
        except ValueError:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} Konfiguracja przerwana (Nieprawidłowa wartość).\n\n"
                f"Wiadomość zostanie usunięta automatycznie za **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer()
            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        if message_limit == 0:
            embed.title = f"{Emojis.REDBUTTON.value} Konfiguracja wstrzymana."
            embed.description = (
                f"{Emojis.REPLY.value} *Konfiguracja przerwana (Nieprawidłowa wartość).\n\n"
                f"Wiadomość zostanie usunięta automatycznie za* **20s.**"
            )
            embed.colour = Color.red()
            embed.set_footer()
            await interaction.edit_original_message(embed=embed)
            return await interaction.delete_original_message(delay=20)

        await self.bot.db.execute_fetchone(
            "INSERT INTO antyflood(guild_id, messages_limit) VALUES(?,?)",
            (interaction.guild.id, message_limit),
        )

        embed = Embed(
            title=f"Pomyślnie włączono AntyFlood {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} *AntyFlood nie działa dla osób z permisją `Manage_Messages`!*",
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        await interaction.edit_original_message(embed=embed)

    @antyflood.subcommand(name="wyłącz", description="Wyłącza system AntyFlood")  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def antyflood_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM antyflood WHERE guild_id = ?", (interaction.guild.id,)
        )

        if not response:
            return await interaction.send_error_message(description="AntyFlood już jest wyłączony.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM antyflood WHERE guild_id = ?", (interaction.guild.id,)
        )

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono AntyFlood {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} System AntyFlood został wyłączony.",
            color=Color.green(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandAntyFlood(bot))
