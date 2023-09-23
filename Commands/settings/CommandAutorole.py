from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from nextcord import Color, Member, Role, SlashOption
from nextcord import errors as nextcord_errors
from nextcord import slash_command

from converters import MessageConverter
from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord import Message

    from bot import Smiffy
    from typings import DB_RESPONSE


class CommandAutorole(CustomCog):
    @slash_command(name="autorole")
    async def autorole(self, interaction: CustomInteraction):
        ...

    @autorole.subcommand(
        name="reactionrole",
        description="Bot tworzy nową reactionrole.",
        dm_permission=False,
    )  # pyright: ignore
    @PermissionHandler(manage_roles=True)
    async def reactionrole(
        self,
        interaction: CustomInteraction,
        emoji: str = SlashOption(
            name="emotka",
            description="Podaj emoji której chcesz użyć do reactionrole",
        ),
        role: Role = SlashOption(
            name="rola",
            description="Wybierz rolę którą chcesz nadawać",
        ),
        message_id: str = SlashOption(
            name="id_wiadomości",
            description="Wpisz ID wiadomości do której chcesz dodać reactionrole",
        ),
    ):
        assert interaction.guild
        assert isinstance(interaction.user, Member)

        message: Optional[Message] = await MessageConverter().convert(interaction, message_id)

        if not message:
            return await interaction.send_error_message(
                description="Nie odnalazłem podanej wiadomości. Wprowadź prawidłowe ID lub link do wiadomości."
            )

        if role.is_bot_managed() or role.is_default() or role.is_premium_subscriber():
            return await interaction.send_error_message(description="Podana rola nie może zostać użyta.")

        if not role.is_assignable():
            return await interaction.send_error_message(
                description="Podana rola posiada większe uprawnienia od bota."
            )

        try:
            await message.add_reaction(emoji)
        except (
            nextcord_errors.HTTPException,
            nextcord_errors.InvalidArgument,
        ):
            return await interaction.send_error_message(description="Podane emoji nie może zostać użyte.")

        if interaction.user.id != interaction.guild.owner_id:
            if role.position >= interaction.user.top_role.position:
                return await interaction.send_error_message(
                    description="Podana rola posiada większe uprawnienia od ciebie."
                )

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM reactionroles WHERE guild_id = ? AND message_id = ? AND role_id = ? AND emoji = ?",
            (
                interaction.guild.id,
                message.id,
                role.id,
                emoji,
            ),
        )
        if response:
            return await interaction.send_error_message(
                description="Identyczny reactionrole już jest przypisany do podanej wiadmości."
            )

        await self.bot.db.execute_fetchone(
            "INSERT INTO reactionroles(guild_id, channel_id, message_id, role_id, emoji) VALUES(?,?,?,?,?)",
            (
                interaction.guild.id,
                message.channel.id,
                message.id,
                role.id,
                str(emoji),
            ),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie dodano ReactionRole {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Reaction role został dodany.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandAutorole(bot))
