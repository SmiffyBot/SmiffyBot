from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from ast import literal_eval

from nextcord import Embed, Color, utils, slash_command, SlashOption, Role, errors
from nextcord.ext.application_checks import check

from utilities import CustomInteraction, CustomCog
from enums import Emojis

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


def is_guild_owner():
    def predicate(interaction: CustomInteraction) -> bool:
        assert interaction.guild
        assert interaction.user

        return interaction.user.id == interaction.guild.owner_id

    return check(predicate)  # pyright: ignore


class CommandPermissions(CustomCog):
    supported_commands: dict[str, str] = {
        "Komenda Ban": "ban",
        "Komenda TempBan": "tempban",
        "Komenda Unban": "unban",
        "Komenda Kick": "kick",
        "Komenda Mute": "mute",
        "Komenda Unmute": "unmute",
        "Komenda Slowmode": "slowmode",
        "Komenda Clear": "clear",
        "Komenda Warny": "warn",
        "Komenda KaryWarny": "karywarny",
        "Komenda Konkurs": "konkurs",
        "Komenda Ankieta": "poll",
        "Komenda AutoResponder": "autoresponder",
    }

    @slash_command(name="uprawnienia", dm_permission=False)
    async def permission(self, interaction: CustomInteraction) -> None:
        pass

    @permission.subcommand(name="dodaj", description="Dodaj uprawnienia dla roli podanej komendy")
    @is_guild_owner()
    async def permission_add(
        self,
        interaction: CustomInteraction,
        command: str = SlashOption(
            name="komenda",
            description="Wybierz komendę która chcesz dodać do uprawnien roli",
            choices=supported_commands,
        ),
        role: Role = SlashOption(
            name="rola",
            description="Wybierz rolę do której chcesz przypisać uprawnienie",
        ),
    ):
        assert interaction.guild

        if role.is_bot_managed() or role.is_default():
            return await interaction.send_error_message(description="Nie możesz użyć tej roli.")

        command_mention: str = interaction.get_command_mention(command_name=command)

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM permissions WHERE guild_id = ? AND role_id = ?",
            (interaction.guild.id, role.id),
        )

        if response:
            permissions_data: list[str] = literal_eval(response[2])
            if command not in permissions_data:
                permissions_data.append(command)
                await self.bot.db.execute_fetchone(
                    "UPDATE permissions SET permissions_data = ? WHERE guild_id = ? AND role_id = ?",
                    (str(permissions_data), interaction.guild.id, role.id),
                )
            else:
                return await interaction.send_error_message(
                    description=f"Podana rola już ma uprawnienia do komendy `/{command_mention}`"
                )
        else:
            permissions_data: list[str] = [command]
            await self.bot.db.execute_fetchone(
                "INSERT INTO permissions(guild_id, role_id, permissions_data) VALUES(?,?,?)",
                (interaction.guild.id, role.id, str(permissions_data)),
            )

        return await interaction.send_success_message(
            title=f"Pomyślnie zaktualizowano uprawnienia {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Rola: {role.mention} uzyskała uprawnienia do komendy {command_mention}",
        )

    @permission_add.error  # pyright: ignore
    async def permission_add_error(self, interaction: CustomInteraction, error):
        if isinstance(error, errors.ApplicationCheckFailure):
            return await interaction.send_error_message(
                description="Tylko właściciel serwera może użyć tej komendy."
            )

    @permission.subcommand(name="usuń", description="Usuń uprawnienia roli do podanej komendy")
    @is_guild_owner()
    async def permission_remove(
        self,
        interaction: CustomInteraction,
        command: str = SlashOption(
            name="komenda",
            description="Wybierz komendę dla której chcesz usunąć uprawnienia",
            choices=supported_commands,
        ),
        role: Role = SlashOption(name="rola", description="Wybierz rolę której chcesz usunąć uprawnienie"),
    ):
        assert interaction.guild

        if role.is_bot_managed() or role.is_default():
            return await interaction.send_error_message(description="Nie możesz użyć tej roli")

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM permissions WHERE guild_id = ? AND role_id = ?",
            (interaction.guild.id, role.id),
        )
        if response:
            role_permissions: list[str] = literal_eval(response[2])
            if command in role_permissions:
                role_permissions.remove(command)

                await self.bot.db.execute_fetchone(
                    "UPDATE permissions SET permissions_data = ? WHERE guild_id = ? AND role_id = ?",
                    (str(role_permissions), interaction.guild.id, role.id),
                )

                command_mention: str = interaction.get_command_mention(command_name=command)

                return await interaction.send_success_message(
                    title=f"Pomyślnie zaktualizowano {Emojis.GREENBUTTON.value}",
                    color=Color.green(),
                    description=f"{Emojis.REPLY.value} Usunięto uprawnienia roli: {role.mention} "
                    f"do komendy: {command_mention}",
                )

        return await interaction.send_error_message(
            description=f"Podana komenda nie jest przypisana do uprawnień roli: {role.mention}"
        )

    @permission_remove.error  # pyright: ignore
    async def permission_remove_error(self, interaction: CustomInteraction, error):
        if isinstance(error, errors.ApplicationCheckFailure):
            return await interaction.send_error_message(
                description="Tej komendy może użyć tylko właściciel serwera!"
            )

    @permission.subcommand(name="lista", description="Lista uprawnień dla podanej roli")
    @is_guild_owner()
    async def permission_list(
        self,
        interaction: CustomInteraction,
        role: Role = SlashOption(name="rola", description="Podaj rolę, której chcesz sprawdzić uprawnienia"),
    ):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT permissions_data FROM permissions WHERE guild_id = ? AND role_id = ?",
            (interaction.guild.id, role.id),
        )

        if not response or response[0] == "[]":
            return await interaction.send_error_message(
                description="Podana rola nie posiada żadnych przypisanych uprawnień."
            )

        permissions: list[str] = literal_eval(response[0])

        description: str = ", ".join(
            [interaction.get_command_mention(command_name=cmd) for cmd in permissions]
        )

        embed = Embed(
            title="`📝` Lista uprawnień przypisanych do roli",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Uprawnienia roli: {role.mention}\n\n" + description,
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)
        await interaction.send(embed=embed)

    @permission_list.error  # pyright: ignore
    async def permission_list_error(self, interaction: CustomInteraction, error):
        if isinstance(error, errors.ApplicationCheckFailure):
            return await interaction.send_error_message(
                description="Tej komendy może użyć tylko właściciel serwera!"
            )


def setup(bot: Smiffy):
    bot.add_cog(CommandPermissions(bot))
