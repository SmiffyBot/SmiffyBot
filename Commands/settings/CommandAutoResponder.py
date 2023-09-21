from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Iterable, Optional

from nextcord import (
    Attachment,
    Color,
    Embed,
    SlashOption,
    TextInputStyle,
    slash_command,
    ui,
    utils,
)

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class ReplyAnswerModal(ui.Modal):
    def __init__(self, text: str, value: str, image: Optional[Attachment]):
        super().__init__("Odpowiedź bota")

        self.text, self.value = text, value
        self.image: Optional[Attachment] = image

        self.answer = ui.TextInput(
            label="Podaj treść odpowiedzi na wpisaną wiadomość",
            style=TextInputStyle.paragraph,
            required=True,
            max_length=1600,
            min_length=1,
        )
        self.add_item(self.answer)

    async def callback(self, interaction: CustomInteraction):
        assert interaction.guild

        if not self.answer.value:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        await interaction.response.defer()

        image_bytes: Optional[bytes] = None

        if self.image:
            file = BytesIO(await self.image.read())
            image_bytes = file.read()

        bot: Smiffy = interaction.bot

        response: Iterable[DB_RESPONSE] = await bot.db.execute_fetchall(
            "SELECT * FROM autoresponder WHERE guild_id = ?", (interaction.guild.id,)
        )

        for data in response:
            if data[1] == self.text.lower():
                return await interaction.send_error_message(
                    description="Bot już ma ustawioną odpowiedź na tą wiadomość."
                )

        if len(response) >= 25:  # pyright: ignore
            return await interaction.send_error_message(
                description="> Osiągnięto limit `25` automatycznych odpowiedzi bota na serwerze."
            )

        await bot.db.execute_fetchall(
            "INSERT INTO autoresponder(guild_id, message_content, option, reply_content, reply_image) "
            "VALUES(?,?,?,?,?)",
            (
                interaction.guild_id,
                self.text.lower(),
                self.value,
                self.answer.value,
                image_bytes,
            ),
        )

        description: str = (
            f"`✏️` **Słowo**\n{Emojis.REPLY.value} {self.text.replace('`', '')}\n\n"
            f"`📝` **Odpowiedź**\n{Emojis.REPLY.value} {self.answer.value.replace('`', '')}"
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie dodano AutoResponder {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=description,
        )


class CommandAutoResponder(CustomCog):
    @slash_command(name="autoresponder", dm_permission=False)
    async def autoresponder(self, interaction: CustomInteraction):
        pass

    @autoresponder.subcommand(  # pyright: ignore
        name="dodaj", description="Dodaj automatyczną odpowiedź bota"
    )
    @PermissionHandler(manage_messages=True, user_role_has_permission="autoresponder")
    async def autoresponder_add(
        self,
        interaction: CustomInteraction,
        text: str = SlashOption(
            name="tekst",
            description="Podaj tekst na który bot ma reagować",
            max_length=300,
        ),
        value: str = SlashOption(
            name="opcja",
            description="Wybierz kiedy bot ma reagować",
            choices={
                "Zawiera tekst": "in",
                "Wiadomość zaczynająca się od tekstu": "start",
                "Wiadomość taka sama jak tekst": "equals",
            },
        ),
        image: Optional[Attachment] = SlashOption(
            name="obraz", description="Obraz dołączony do odpowiedzi bota"
        ),
    ):
        if image and image.content_type not in ("image/jpeg", "image/png"):
            return await interaction.send_error_message(
                description="Obraz musi być w formacie `jpg` lub `.png`"
            )

        await interaction.response.send_modal(ReplyAnswerModal(text, value, image))

    @autoresponder.subcommand(name="usuń", description="Usuwa automatyczną odpowiedź bota")  # pyright: ignore
    @PermissionHandler(manage_messages=True, user_role_has_permission="autoresponder")
    async def autoresponder_remove(
        self,
        interaction: CustomInteraction,
        message_content: str = SlashOption(
            name="wiadomość",
            description="Wybierz automatyczną wiadomość którą chcesz usunąć",
            max_length=300,
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM autoresponder WHERE guild_id = ? AND message_content = ?",
            (interaction.guild.id, message_content.lower()),
        )

        if not response:
            return await interaction.send_error_message(
                description="Niestety, ale nie odnalazłem takiego AutoRespondera."
            )

        await self.bot.db.execute_fetchone(
            "DELETE FROM autoresponder WHERE guild_id = ? AND message_content = ?",
            (interaction.guild.id, message_content.lower()),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie usunięto AutoResponder {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} **Slowo:** `{message_content.replace('`', '')}`",
        )

    @autoresponder_remove.on_autocomplete("message_content")
    async def autoresponder_remove_autocomplete(
        self, interaction: CustomInteraction, query: Optional[str]
    ) -> Optional[list[str]]:
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM autoresponder WHERE guild_id = ?", (interaction.guild.id,)
        )
        list_of_messages: list[str] = [message_data[1] for message_data in response]

        if not query:
            return list_of_messages[0:25]

        get_near_message: list = [
            message for message in list_of_messages if message.lower().startswith(query.lower())
        ][0:25]
        return get_near_message

    @autoresponder.subcommand(name="info", description="Informacje o obecnych automatycznych odpowiedziach")
    async def autoresponder_info(
        self,
        interaction: CustomInteraction,
        message_content: str = SlashOption(
            name="wiadomość",
            description="Wybierz wiadomość którą chcesz sprawdzić",
            max_length=300,
        ),
    ):
        assert interaction.guild

        await interaction.response.defer()

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM autoresponder WHERE guild_id = ? AND message_content = ?",
            (interaction.guild.id, message_content.lower()),
        )

        if not response:
            return await interaction.send_error_message(
                description="Niestety, ale nie odnalazłem takiego AutoRespondera."
            )

        embed = Embed(
            title="`📕` AutoResponder Informacje",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user_avatar_url)
        embed.set_thumbnail(url=interaction.guild_icon_url)

        embed.add_field(
            name="`🗨️` Wiadomość",
            value=f"{Emojis.REPLY.value} {message_content}",
            inline=False,
        )

        embed.add_field(
            name="`🔖` Odpowiedź",
            value=f"{Emojis.REPLY.value} {response[3]}",
            inline=False,
        )

        for text, option in {
            "Zawiera tekst": "in",
            "Wiadomość zaczynająca się od tekstu": "start",
            "Wiadomość taka sama jak tekst": "equals",
        }.items():
            if option == response[2]:
                embed.add_field(name="`⚙️` Ustawienie", value=f"{Emojis.REPLY.value} {text}")
                break

        await interaction.send(embed=embed)

    @autoresponder_info.on_autocomplete("message_content")
    async def info_autocomplete(
        self, interaction: CustomInteraction, query: Optional[str]
    ) -> Optional[list[str]]:
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM autoresponder WHERE guild_id = ?", (interaction.guild.id,)
        )
        list_of_messages: list[str] = [message_data[1] for message_data in response]

        if not query:
            return list_of_messages[0:25]

        get_near_message: list = [
            message for message in list_of_messages if message.lower().startswith(query.lower())
        ][0:25]
        return get_near_message


def setup(bot: Smiffy):
    bot.add_cog(CommandAutoResponder(bot))
