from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import SlashOption, slash_command
from nextcord.ext.application_checks import errors, is_owner

from enums import Emojis
from utilities import CustomCog, CustomInteraction

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import DB_RESPONSE, Optional


class CommandGlobalBan(CustomCog):
    @slash_command(name="globalban", dm_permission=False)
    async def global_ban(self, interaction: CustomInteraction):
        pass

    @global_ban.subcommand(name="nadaj", description="Nadaję globalnego bana dla podanej osoby")
    @is_owner()
    async def global_ban_add(
        self,
        interaction: CustomInteraction,
        user_id: str = SlashOption(name="id_osoby", description="Podaj id osoby"),
        reason: str = SlashOption(name="powód", description="Podaj powód blokady"),
    ):
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM global_bans WHERE user_id = ?", (int(user_id),)
        )
        if response:
            return await interaction.send_error_message(description="Podana osoba już posiada blokadę.")

        await self.bot.db.execute_fetchone(
            "INSERT INTO global_bans(user_id, reason) VALUES(?,?)",
            (int(user_id), reason),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie nadano blokadę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Blokada dla id: `{user_id}` została nadana.",
        )

    @global_ban.subcommand(name="usuń", description="Usuwa globalną blokade")
    @is_owner()
    async def global_ban_remove(
        self,
        interaction: CustomInteraction,
        user_id: str = SlashOption(name="id_osoby", description="Podaj id osoby"),
    ):
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM global_bans WHERE user_id = ?", (int(user_id),)
        )
        if not response:
            return await interaction.send_error_message(description="Podana osoba nie posiada blokady.")

        await self.bot.db.execute_fetchone("DELETE FROM global_bans WHERE user_id = ?", (int(user_id),))

        await interaction.send_success_message(
            title=f"Pomyślnie zdjęto blokadę {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pomyślnie usunięto blokade osobie: `{user_id}`",
        )

    @global_ban.error  # pyright: ignore[reportGeneralTypeIssues]
    async def global_ban_error(self, interaction: CustomInteraction, error: Exception):
        if isinstance(error, errors.ApplicationNotOwner):
            return await interaction.send_error_message(
                description="Tylko właściciel bota może użyć tej komendy."
            )


def setup(bot: Smiffy):
    bot.add_cog(CommandGlobalBan(bot))
