from __future__ import annotations

from ast import literal_eval
from typing import TYPE_CHECKING, Iterable, Optional

from nextcord import (
    ButtonStyle,
    Color,
    Embed,
    Member,
    SlashOption,
    TextChannel,
    TextInputStyle,
    Thread,
)
from nextcord import errors as nc_errors
from nextcord import slash_command, ui, utils
from nextcord.abc import GuildChannel

from converters import MessageConverter
from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord import Guild, Message

    from bot import Smiffy
    from typings import DB_RESPONSE


class DecisionFormView(ui.View):
    def __init__(
        self,
        user: Optional[Member] = None,
        form_id: Optional[str] = None,
    ):
        super().__init__(timeout=None)

        self.form_id: Optional[str] = form_id
        self.user: Optional[Member] = user

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert isinstance(interaction.user, Member)

        if interaction.user.guild_permissions.manage_channels:
            return True

        await interaction.send_error_message(
            description="Nie posiadasz permisji: `Manage_Channels`, aby móc tego uyżyć.",
            ephemeral=True,
        )
        return False

    @ui.button(  # pyright: ignore
        label="Zaakceptuj",
        style=ButtonStyle.green,
        emoji=Emojis.GREENBUTTON.value,
        custom_id="accept-form",
    )
    async def accept_button(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        bot: Smiffy = interaction.client

        assert bot.user and interaction.message and interaction.user and interaction.guild

        for embed in interaction.message.embeds:
            if not isinstance(embed.description, str):
                embed.description = str()

            embed.colour = Color.green()
            embed.title = "Formularz zaakceptowany <a:success:984490514332139600>"
            embed.description += f"\n─────\nAkceptujący: {interaction.user.mention} | ({interaction.user})"
            await interaction.message.edit(embed=embed, view=None)
            break

        if self.user and self.form_id:
            response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT notify FROM forms WHERE guild_id = ? AND form_id = ?",
                (
                    interaction.guild.id,
                    self.form_id,
                ),
            )
            if response and response[0] and response[0] == "on":
                embed = Embed(
                    title=f"Twój formularz został zaakceptowany {Emojis.GREENBUTTON.value}",
                    color=Color.green(),
                    timestamp=utils.utcnow(),
                )
                embed.set_author(
                    name=f"{bot.user.name} - Formularze",
                    icon_url=interaction.user_avatar_url,
                )

                embed.set_thumbnail(url=interaction.guild_icon_url)

                embed.add_field(
                    name="`⚙️` Serwer",
                    value=f"{Emojis.REPLY.value} `{interaction.guild}`",
                    inline=False,
                )
                embed.add_field(
                    name="`🌴` Odrzucający",
                    value=f"{Emojis.REPLY.value} `{interaction.user}`",
                    inline=False,
                )
                embed.add_field(
                    name="`📌` Formularz",
                    value=f"{Emojis.REPLY.value} `{self.form_id}`",
                )

                try:
                    await self.user.send(embed=embed)
                except (
                    nc_errors.HTTPException,
                    nc_errors.Forbidden,
                ):
                    pass

        await interaction.send_success_message(
            title=f"Pomyślnie zaakceptowano {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Formularz został pomyślnie zaakceptowany.",
            ephemeral=True,
        )

    @ui.button(  # pyright: ignore
        label="Odrzuć",
        style=ButtonStyle.red,
        emoji=Emojis.REDBUTTON.value,
        custom_id="decline-form",
    )
    async def decline_button(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        bot: Smiffy = interaction.client

        assert interaction.guild and interaction.message and bot.user and interaction.user

        for embed in interaction.message.embeds:
            if not isinstance(embed.description, str):
                embed.description = str()

            embed.colour = Color.red()
            embed.title = f"Formularz odrzucony {Emojis.REDBUTTON.value}"
            embed.description += f"\n─────\nOdrzucający: {interaction.user.mention} | ({interaction.user})"
            await interaction.message.edit(embed=embed, view=None)
            break

        if self.user and self.form_id:
            response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT notify FROM forms WHERE guild_id = ? AND form_id = ?",
                (
                    interaction.guild.id,
                    self.form_id,
                ),
            )
            if response and response[0] and response[0] == "on":
                embed = Embed(
                    title=f"Twój formularz został odrzucony {Emojis.REDBUTTON.value}",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                )
                embed.set_author(
                    name=f"{bot.user.name} - Formularze",
                    icon_url=interaction.user_avatar_url,
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)

                embed.add_field(
                    name="`⚙️` Serwer",
                    value=f"{Emojis.REPLY.value} `{interaction.guild}`",
                    inline=False,
                )
                embed.add_field(
                    name="`🌴` Odrzucający",
                    value=f"{Emojis.REPLY.value} `{interaction.user}`",
                    inline=False,
                )
                embed.add_field(
                    name="`📌` Formularz",
                    value=f"{Emojis.REPLY.value} `{self.form_id}`",
                )

                try:
                    await self.user.send(embed=embed)
                except (
                    nc_errors.HTTPException,
                    nc_errors.Forbidden,
                ):
                    pass

        await interaction.send_success_message(
            title=f"Pomyślnie odrzucono {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"{Emojis.REPLY.value} Formularz został pomyślnie odrzucony.",
            ephemeral=True,
        )


class FormModal(ui.Modal):
    def __init__(self, guild_id: int, db_data: DB_RESPONSE):
        form_id: str = db_data[1]

        super().__init__(title=form_id)

        self.form_id: str = form_id
        self.guild_id: int = guild_id
        self.db_data: DB_RESPONSE = db_data

        self.questions: tuple[str | None, ...] = literal_eval(db_data[6])

        for question in self.questions:
            if question is None:
                continue

            question_input = ui.TextInput(
                label=question,
                style=TextInputStyle.paragraph,
                required=True,
                max_length=1000,
                custom_id=question,
            )
            self.add_item(question_input)

    async def callback(self, interaction: CustomInteraction):
        if not interaction.data or not isinstance(interaction.channel, TextChannel):
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        bot: Smiffy = interaction.bot
        assert isinstance(interaction.user, Member) and bot.user

        await interaction.response.defer()

        components: list[dict[str, list]] = interaction.data["components"]  # pyright: ignore

        guild: Optional[Guild] = await bot.getch_guild(self.guild_id)
        channel: Optional[GuildChannel] = await bot.getch_channel(self.db_data[2])

        if not guild or not isinstance(channel, TextChannel):
            return await interaction.send_error_message(
                description="Wystąpił błąd z danymi tego formularza. Spróbuj ponownie.",
                ephemeral=True,
            )

        if self.db_data[4] == "on":
            try:
                await interaction.channel.set_permissions(
                    interaction.user,
                    send_messages=False,
                )
            except (
                nc_errors.HTTPException,
                nc_errors.Forbidden,
                nc_errors.NotFound,
            ):
                pass

        embed = Embed(
            title="<:notify:1146668022518521888> Otrzymano nowy formularz",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"Przesyłający: {interaction.user.mention} | ({interaction.user})",
        )
        embed.set_author(
            name=f"{bot.user.name} - {self.form_id}",
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        for component in components:
            component_data: dict[str, str | int] = component["components"][0]

            question_answer: str = str(component_data["value"])
            question_text: str = str(component_data["custom_id"])

            embed.add_field(
                name=f"<:dot:1017090468795908281> {question_text}",
                value=f"{Emojis.REPLY.value} {question_answer}",
                inline=False,
            )

        decisionView = DecisionFormView(interaction.user, self.form_id)

        try:
            await channel.send(embed=embed, view=decisionView)
        except (
            nc_errors.Forbidden,
            nc_errors.HTTPException,
        ):
            return await interaction.send_error_message(
                description="Wystąpił błąd z przesyłaniem Twojego formularzu. Spróbuj ponownie.",
                ephemeral=True,
            )

        await interaction.send_success_message(
            title=f"Pomyślnie przesłano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Twój formularz został pomyślnie wysłany.",
            ephemeral=True,
        )


class SubmitFormView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(  # pyright: ignore
        label="Wypełnij",
        style=ButtonStyle.green,
        emoji="<a:success:984490514332139600>",
        custom_id="submit-form",
    )
    async def submit_button(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        assert interaction.guild

        if not interaction.message:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        bot: Smiffy = interaction.bot

        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT * FROM forms WHERE guild_id = ? AND message_id = ?",
            (
                interaction.guild.id,
                interaction.message.id,
            ),
        )

        if not response:
            return await interaction.send_error_message(
                description="Wystąpił błąd z danymi tego formularza. Spróbuj ponownie.",
                ephemeral=True,
            )

        modal: FormModal = FormModal(interaction.guild.id, response)
        await interaction.response.send_modal(modal)


class CommandForms(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot)
        self.bot.loop.create_task(self.update_views())

    async def update_views(self):
        self.bot.add_view(DecisionFormView())
        self.bot.add_view(SubmitFormView())

    @slash_command(name="formularz", dm_permission=False)
    async def form(self, interaction: CustomInteraction):
        pass

    @form.subcommand(
        name="stwórz",
        description="Tworzy nowy system formularzu",
    )  # pyright: ignore
    @PermissionHandler(manage_channels=True)
    async def form_create(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanal",
            description="Podaj kanał na które mają być wysyłane podania",
        ),
        name: str = SlashOption(
            name="nazwa_formularza",
            description="Podaj nazwę formularza",
            max_length=45,
        ),
        block: str = SlashOption(
            name="blokada_kanalu_po_wyslaniu",
            description="Ustaw czy bot ma blokować kanał osobie która już przesłała formularz.",
            choices={"Tak": "on", "Nie": "off"},
        ),
        notify: str = SlashOption(
            name="wyniki_powiadomienia_pv",
            description="Jeśli włączysz tą opcje, " "to bot będzie informował osobę o wyniku swojego podania",
            choices={
                "Włącz": "on",
                "Wyłącz": "off",
            },
        ),
        question_1: str = SlashOption(
            name="pytanie_1",
            description="Podaj treść pierwszego pytania",
            max_length=45,
        ),
        question_2: Optional[str] = SlashOption(
            name="pytanie_2",
            description="Podaj treść drugiego pytania",
            max_length=45,
        ),
        question_3: Optional[str] = SlashOption(
            name="pytanie_3",
            description="Podaj treść trzeciego pytania",
            max_length=45,
        ),
        question_4: Optional[str] = SlashOption(
            name="pytanie_4",
            description="Podaj treść czwartego pytania",
            max_length=45,
        ),
        question_5: Optional[str] = SlashOption(
            name="pytanie_5",
            description="Podaj treść piątego pytania",
            max_length=45,
        ),
    ):
        assert (
            isinstance(
                interaction.channel,
                (Thread, TextChannel),
            )
            and interaction.guild
        )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM forms WHERE guild_id = ? AND form_id = ?",
            (interaction.guild.id, name),
        )
        if response:
            return await interaction.send_error_message(
                description="Wybrana nazwa formularza już istnieje. Usuń formularz o tej nazwie lub zmień jego nazwe."
            )

        await interaction.response.defer(ephemeral=True)

        embed = Embed(
            title=f"{name}",
            color=Color.dark_theme(),
            description="> Naciśnij poniższy przycisk, aby wypełnić formularz",
            timestamp=utils.utcnow(),
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_footer(text="Made by SmiffyBot")

        button: SubmitFormView = SubmitFormView()
        message: Message = await interaction.channel.send(embed=embed, view=button)

        questions: tuple[str | None, ...] = (
            question_1,
            question_2,
            question_3,
            question_4,
            question_5,
        )

        await self.bot.db.execute_fetchone(
            "INSERT INTO forms(guild_id, form_id, channel_id, message_id, block, notify, questions) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                interaction.guild.id,
                name,
                channel.id,
                message.id,
                block,
                notify,
                str(questions),
            ),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie utworzono formularz {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Formularz został pomyślnie utworzony.",
            ephemeral=True,
        )

    @form.subcommand(
        name="usuń",
        description="Usuwa wybrany formularz",
    )  # pyright: ignore
    @PermissionHandler(manage_channels=True)
    async def form_delete(
        self,
        interaction: CustomInteraction,
        form_name: str = SlashOption(
            name="nazwa_formularza",
            description="Podaj nazwę formularza",
            max_length=45,
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM forms WHERE guild_id = ? AND form_id = ?",
            (interaction.guild.id, form_name),
        )

        if not response:
            return await interaction.send_error_message(
                description=f"Niestety, ale nie odnalazłem formularza o nazwie: `{form_name}`"
            )

        message: Optional[Message] = await MessageConverter().convert(interaction, str(response[3]))
        if message:
            await message.delete()

        await self.bot.db.execute_fetchone(
            "DELETE FROM forms WHERE guild_id = ? AND form_id = ?",
            (interaction.guild.id, form_name),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie usunięto formularz {Emojis.GREENBUTTON.value}",
            color=Color.dark_theme(),
            description=f"{Emojis.REPLY.value} Nazwa formularza: `{form_name}`",
        )

    @form_delete.on_autocomplete("form_name")
    async def message_content_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ) -> Optional[list[str]]:
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM forms WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        if not response:
            return

        forms: list[str] = [db_data[1] for db_data in response]
        if not query:
            return forms[0:25]

        get_near_message: list[str] = [
            form_name for form_name in forms if form_name.lower().startswith(query.lower())
        ]

        return get_near_message[0:25]


def setup(bot: Smiffy):
    bot.add_cog(CommandForms(bot))
