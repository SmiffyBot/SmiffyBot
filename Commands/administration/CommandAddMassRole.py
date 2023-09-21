from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Member, Role, SlashOption, errors, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandAddMassRole(CustomCog):
    @slash_command(
        name="nadajmasoworole",
        description="Nadaje każdemu wybraną role",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(manage_roles=True)
    async def addmassrole(
        self,
        interaction: CustomInteraction,
        role: Role = SlashOption(
            name="rola",
            description="Podaj kanał rolę, którą chcesz nadać",
        ),
    ):
        assert interaction.guild and interaction.user

        await interaction.response.defer()

        if interaction.guild.me.top_role.position <= role.position:
            return await interaction.send_error_message(
                description="Podana rola posiada większe uprawnienia ode mnie."
            )

        if isinstance(interaction.user, Member):
            if interaction.user.top_role.position <= role.position:
                return await interaction.send_error_message(
                    description=f"Rola: {role.mention} posiada większe uprawnienia od ciebie.",
                )

        if role.is_default() or role.is_bot_managed() or role.is_premium_subscriber():
            return await interaction.send_error_message(description="Podana rola nie może zostać użyta.")

        for member in interaction.guild.members:
            try:
                if role not in member.roles:
                    await member.add_roles(
                        role,
                        reason="Smiffy - AddMassRole",
                    )
            except (
                errors.Forbidden,
                errors.HTTPException,
            ):
                pass

        return await interaction.send_success_message(
            title=f"Pomyślnie nadano role {Emojis.GREENBUTTON.value}",
            description=f"<:reply:1129168370642718833> Nadano role: {role.mention} "
            f"dla `{interaction.guild.member_count}` osób",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandAddMassRole(bot))
