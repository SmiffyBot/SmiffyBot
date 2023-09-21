from __future__ import annotations

from typing import TYPE_CHECKING

from nextcord import Member, SlashOption, slash_command

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy


class CommandUnmute(CustomCog):
    @slash_command(
        name="unmute",
        description="Odcisza użytkownika.",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(
        moderate_members=True,
        user_role_has_permission="unmute",
    )
    async def unmute(
        self,
        interaction: CustomInteraction,
        member: Member = SlashOption(
            name="osoba",
            description="Wybierz osobę którą chcesz odciszyć.",
        ),
    ):
        assert interaction.user and interaction.guild

        await interaction.response.defer()

        if not member.communication_disabled_until:
            return await interaction.send_error_message(
                description=f"{member.mention} nie posiada wyciszenia."
            )

        if isinstance(interaction.guild.me, Member):
            if interaction.guild.me.top_role <= member.top_role or interaction.guild.owner_id == member.id:
                return await interaction.send_error_message(
                    description=f"Użytkownik: {member.mention} posiada większe uprawnienia ode mnie.",
                )

        if isinstance(interaction.user, Member):
            if interaction.user.top_role <= member.top_role or member.id == interaction.guild.owner_id:
                return await interaction.send_error_message(
                    description=f"Twoja rola jest zbyt nisko, aby odciszyć {member.mention}",
                )

        await member.edit(timeout=None)

        await interaction.send_success_message(
            title=f"Pomyślnie odciszono {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Użytkownik: `{member}`",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandUnmute(bot))
