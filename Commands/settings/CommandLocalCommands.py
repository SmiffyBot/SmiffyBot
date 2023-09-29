from asyncio import sleep
from string import punctuation

from nextcord import (
    Color,
    Embed,
    Guild,
    SlashApplicationCommand,
    SlashOption,
    TextInputStyle,
    slash_command,
    ui,
    utils,
)

from bot import Smiffy
from enums import Emojis
from utilities import (
    DB_RESPONSE,
    CustomCog,
    CustomInteraction,
    Iterable,
    Optional,
    PermissionHandler,
)


class ReplyTextModal(ui.Modal):
    def __init__(
        self,
        command_name: str,
        command_description: str,
    ):
        super().__init__(title="Odpowiedź komendy")

        self.text_input = ui.TextInput(
            label="Tekst, którym bot ma odpowiadać",
            style=TextInputStyle.paragraph,
            max_length=2000,
        )
        self.add_item(self.text_input)

        self.name: str = command_name
        self.description: str = command_description

    async def callback(self, interaction: CustomInteraction) -> None:
        assert interaction.guild

        reply_text: Optional[str] = self.text_input.value

        if not reply_text:
            await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")
            return

        command = SlashCommand(
            name=self.name,
            description=self.description,
            guild=interaction.guild,
            bot=interaction.bot,
            reply_text=reply_text,
        )

        command.add_check(func=interaction.bot.check_global_ban)

        await command.setup()

        await interaction.guild.sync_application_commands()

        try:
            command_mention: str = command.get_mention(guild=interaction.guild)
        except ValueError:
            command_mention: str = f"/{command.name}"

        await interaction.send_success_message(
            title=f"Pomyślnie dodano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Komenda: {command_mention} została dodana.",
        )


class SlashCommand(SlashApplicationCommand):
    def __init__(
        self,
        name: str,
        description: str,
        reply_text: str,
        guild: Guild,
        bot: Smiffy,
    ):
        super().__init__(
            name=name,
            description=description,
            callback=self._callback,
            guild_ids=(guild.id,),
        )

        self.reply_text: str = reply_text
        self.name: str = name
        self.description: str = description

        self.guild: Guild = guild
        self.bot: Smiffy = bot

        self.add_check(bot.check_global_ban)

    async def _callback(self, interaction: CustomInteraction):
        return await interaction.send(self.reply_text)

    async def setup(self):
        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM local_commands WHERE guild_id = ? and command_name = ?",
            (self.guild.id, self.name),
        )

        if not response:
            response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
                "INSERT INTO local_commands(guild_id, command_name, command_description, reply_text) VALUES(?,?,?,?)",
                (
                    self.guild.id,
                    self.name,
                    self.description,
                    self.reply_text,
                ),
            )

        self.guild.add_application_command(self, overwrite=True, use_rollout=True)


class CommandLocalCommands(CustomCog):
    def __init__(self, bot: Smiffy):
        super().__init__(bot=bot)

        self.bot.loop.create_task(self.load_local_commands())

    async def load_local_commands(self):
        commands: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall("SELECT * FROM local_commands")

        command_objects: list[SlashCommand] = []
        guilds_to_sync: list[Guild] = []

        for command_data in commands:
            guild_id: int = command_data[0]
            guild: Optional[Guild] = await self.bot.cache.get_guild(guild_id)

            if not guild:
                await self.bot.db.execute_fetchone(
                    "DELETE FROM local_commands WHERE guild_id = ?",
                    (guild_id,),
                )
                continue

            name: str = command_data[1]
            description: str = command_data[2]
            reply_text: str = command_data[3]

            command_objects.append(
                SlashCommand(
                    name=name,
                    description=description,
                    reply_text=reply_text,
                    bot=self.bot,
                    guild=guild,
                )
            )

            if guild not in guilds_to_sync:
                guilds_to_sync.append(guild)

        for command in command_objects:
            await command.setup()
            await sleep(1.5)

        for guild_to_sync in guilds_to_sync:
            await guild_to_sync.sync_application_commands()
            await sleep(1.5)

    @slash_command("lokalnekomendy", dm_permission=False)
    async def local_commands(self, interaction: CustomInteraction) -> None:
        pass

    @local_commands.subcommand(
        name="stwórz",
        description="Tworzy nową lokalną komende.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def local_command_create(
        self,
        interaction: CustomInteraction,
        name: str = SlashOption(
            name="nazwa_komendy",
            description="Podaj nazwę komendy",
            max_length=32,
        ),
        description: str = SlashOption(
            name="opis_komendy",
            description="Opis komendy będzie widoczny " "podczas jej wpisywania",
            max_length=100,
        ),
    ):
        assert interaction.guild

        name = name.lower()

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT command_name FROM local_commands WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if len(response) >= 5:  # pyright: ignore
            return await interaction.send_error_message(description="Osiągnięto limit `5` lokalnych komend.")

        for command_data in response:
            if command_data[0] == name:
                command_mention: str = interaction.get_command_mention(
                    command_name=name,
                    guild=interaction.guild,
                )

                return await interaction.send_error_message(
                    description=f"Lokalna komenda o nazwie: **{command_mention}** już istnieje."
                )

        for command in self.bot.get_all_application_commands():
            if command.name == name and interaction.guild.id not in command.guild_ids:
                command_mention: str = interaction.get_command_mention(command_name=name)

                return await interaction.send_error_message(
                    description=f"Komenda o nazwie: **{command_mention}** już istnieje."
                )

        for letter in name:
            if letter in set(punctuation):
                return await interaction.send_error_message(
                    description=f"Nazwa komendy posiada niedozwolony znak: `{letter}`"
                )

        modal: ReplyTextModal = ReplyTextModal(name, description)
        await interaction.response.send_modal(modal)

    @local_commands.subcommand(
        name="usuń",
        description="Usuwa lokalną komende.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def local_command_delete(
        self,
        interaction: CustomInteraction,
        command_name: str = SlashOption(
            name="nazwa_komendy",
            description="Podaj nazwę komendy",
            max_length=32,
        ),
    ):
        await interaction.response.defer()

        assert interaction.guild

        command_name = command_name.lower()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM local_commands WHERE guild_id = ? AND command_name = ?",
            (interaction.guild.id, command_name),
        )
        if not response:
            return await interaction.send_error_message(description="Podana komenda nie istnieje.")

        for cmd in interaction.guild.get_application_commands():
            if cmd.name == command_name:
                await interaction.guild.delete_application_commands(cmd)

                await self.bot.sync_application_commands()

                await self.bot.db.execute_fetchone(
                    "DELETE FROM local_commands WHERE guild_id = ? AND command_name = ?",
                    (
                        interaction.guild.id,
                        command_name,
                    ),
                )

                return await interaction.send_success_message(
                    title=f"Pomyślnie usunieto {Emojis.GREENBUTTON.value}",
                    color=Color.green(),
                    description=f"{Emojis.REPLY.value} Pomyślnie usunięto komende: `/{command_name}`",
                )

        return await interaction.send_error_message(description="Podana komenda nie istnieje.")

    @local_command_delete.on_autocomplete("command_name")
    async def search_commands(
        self,
        interaction: CustomInteraction,
        search: str,
    ) -> Optional[list[str]]:
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT command_name FROM local_commands WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        command_names: list[str] = [data[0] for data in response]

        if not search:
            return command_names

        get_near_command: list[str] = [
            command for command in command_names if command.lower().startswith(search.lower())
        ]
        return get_near_command

    @local_commands.subcommand(
        name="lista",
        description="Lista lokalnych komend.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def local_commands_list(self, interaction: CustomInteraction):
        commands: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall("SELECT * FROM local_commands")

        if not commands or len(commands) == 0:  # pyright: ignore
            return await interaction.send_error_message(
                description="Na serwerze nie ma aktualnie żadnych lokalnych komend."
            )

        embed = Embed(
            title="`📄` Lista lokalnych komend",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        for command_data in commands:
            command_mention: str = interaction.get_command_mention(
                command_name=command_data[1],
                guild=interaction.guild,
            )

            command_description: str = command_data[2]

            embed.add_field(
                name=f"{command_mention}",
                value=f"{Emojis.REPLY.value} `{command_description}`",
                inline=False,
            )

        await interaction.send(embed=embed)


def setup(bot: Smiffy):
    bot.add_cog(CommandLocalCommands(bot))
