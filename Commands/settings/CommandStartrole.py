from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Member, Role, SlashOption, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandStartRole(CustomCog):
    @slash_command(name="startowarola", dm_permission=False)
    async def startrole(
        self,
        interaction: CustomInteraction,
        dm_permission=False,
    ):  # pylint: disable=unused-argument
        ...

    @startrole.subcommand(  # pyright: ignore
        name="włącz",
        description="Włącza role, która ma być nadawana po wejściu na serwer.",
    )
    @PermissionHandler(manage_guild=True)
    async def startrole_on(
        self,
        interaction: CustomInteraction,
        role: Role = SlashOption(
            name="rola",
            description="Podaj rolę która ma być nadawana.",
        ),
    ):
        assert interaction.guild
        assert isinstance(interaction.user, Member)

        if not role.is_assignable():
            return await interaction.send_error_message(
                description="Nieobsługiwana rola lub mam za małe uprawnienia, aby nadawać tę rolę."
            )

        if (
            role.position > interaction.user.top_role.position
            and interaction.user.id != interaction.guild.owner_id
        ):
            return await interaction.send_error_message(
                description="Podana rola ma większe uprawnienia od ciebie."
            )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM startrole WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if response:
            await self.bot.db.execute_fetchone(
                "UPDATE startrole SET role_id = ? WHERE guild_id = ?",
                (role.id, interaction.guild.id),
            )
        else:
            await self.bot.db.execute_fetchone(
                "INSERT INTO startrole(guild_id, role_id) VALUES(?,?)",
                (interaction.guild.id, role.id),
            )

        await interaction.send_success_message(
            title=f"Pomyślnie ustawiono StartowaRole {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Rola: {role.mention}",
            color=Color.dark_theme(),
        )

    @startrole.subcommand(
        name="wyłącz",
        description="Wyłącza startowarole.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def startrole_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM startrole WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(description="Startowa rola już jest wyłączona.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM startrole WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie wyłączono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Startowa rola została wyłączona.",
            color=Color.dark_theme(),
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandStartRole(bot))
