#  pylint: disable=too-many-lines

from __future__ import annotations

from ast import literal_eval
from asyncio import sleep
from io import BytesIO
from typing import TYPE_CHECKING, Iterable, Optional

from chat_exporter import export, link
from nextcord import (
    AllowedMentions,
    ButtonStyle,
    CategoryChannel,
    Color,
    Embed,
    File,
    Member,
    Message,
    Role,
    SelectOption,
    SlashOption,
    TextChannel,
    TextInputStyle,
    Thread,
    errors,
    slash_command,
    ui,
    utils,
)
from nextcord.abc import GuildChannel

from converters import MessageConverter
from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from typings import DB_RESPONSE


class SelectCloseRole(ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="Wybierz role, które mogą zamknąć ticket (opcjonalne)",
            custom_id="ticket-close-roles",
            max_values=10,
        )

    async def callback(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member)

        await interaction.response.defer(ephemeral=True)

        for role in self.values.roles:
            if role.position > interaction.user.top_role.position:
                return await interaction.send_error_message(
                    description=f"Nie możesz użyć roli: `{role}`\n> *Rola posiada większe uprawnienia od ciebie*",
                    ephemeral=True,
                )

            if role.is_bot_managed():
                return await interaction.send_error_message(
                    description=f"Nie możesz użyć roli: `{role}`\n> *Rola przypisana do bota*",
                    ephemeral=True,
                )


class CloseTicketButtonView(ui.View):
    def __init__(
        self,
        disabled: bool = True,
        title: str = "Zamknij ticket!",
    ):
        super().__init__(timeout=None)

        class CloseTicketButton(ui.Button):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            async def callback(
                self,
                interaction: CustomInteraction,
            ) -> None:
                assert interaction.guild and interaction.user
                assert isinstance(
                    interaction.channel,
                    (TextChannel, Thread),
                )

                await interaction.response.defer()

                bot: Smiffy = interaction.bot

                channel_name: str = (interaction.channel.name.split("-"))[0].lower()

                response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                    "SELECT ticket_close_roles FROM tickets_close WHERE guild_id = ? AND channel_name = ?",
                    (
                        interaction.guild.id,
                        channel_name,
                    ),
                )

                if response and response[0]:
                    if interaction.guild.owner_id == interaction.user.id:
                        return await self.close_ticket(interaction)

                    roles_list: list[int] = literal_eval(response[0])
                    if roles_list:
                        roles: list[Role | None] = [
                            await bot.cache.get_role(
                                interaction.guild.id,
                                role_id,
                            )
                            for role_id in roles_list
                        ]

                        for role in roles:
                            if role and interaction.user in role.members:
                                return await self.close_ticket(interaction)

                        await interaction.send_error_message(
                            description="Wygląda na to, że nie posiadasz wystarczających uprawnień, "
                            "aby zamknąć ten ticket.",
                            ephemeral=True,
                        )
                        return
                else:
                    await self.close_ticket(interaction)

            @staticmethod
            async def close_ticket(
                interaction: CustomInteraction,
            ):
                assert interaction.guild and interaction.message

                assert isinstance(
                    interaction.channel,
                    (TextChannel, Thread),
                )

                ticket_title: Optional[str] = None
                for embed in interaction.message.embeds:
                    ticket_title = embed.title
                    break

                if not ticket_title:
                    return

                await interaction.message.edit(view=None)

                seconds = 5

                embed = Embed(
                    title=f"{Emojis.REDBUTTON.value} Zamykanie {ticket_title}",
                    color=Color.red(),
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Zamykanie: `{seconds}s`\n\n- Wywołanie: `{interaction.user}`",
                )
                embed.set_thumbnail(url=interaction.guild_icon_url)
                embed.set_author(
                    name=interaction.user,
                    icon_url=interaction.user_avatar_url,
                )

                message = await interaction.send(embed=embed)

                for _ in range(5):
                    seconds -= 1
                    embed.description = (
                        f"{Emojis.REPLY.value} Zamykanie: `{seconds}s`\n\n"
                        f"- Wywołanie: `{interaction.user}`"
                    )
                    await message.edit(embed=embed)

                    await sleep(1)

                channel_name: str = (interaction.channel.name.split("-"))[0].lower()
                bot: Smiffy = interaction.bot

                response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                    "SELECT transcript_channel FROM tickets WHERE guild_id = ? AND channel_name = ?",
                    (
                        interaction.guild.id,
                        channel_name,
                    ),
                )

                if response and response[0]:
                    transcript: str = await export(interaction.channel)
                    if transcript:
                        transcript_file = File(
                            BytesIO(transcript.encode()),
                            filename=f"transcript-{interaction.channel.id}.html",
                        )
                        channel: Optional[GuildChannel] = await bot.cache.get_channel(
                            interaction.guild.id, response[0]
                        )

                        if not isinstance(channel, TextChannel):
                            return

                        message_transcript = await channel.send(file=transcript_file)
                        transcript_link: str = await link(message_transcript)

                        embed = Embed(
                            title=f"Transcript: {ticket_title}",
                            description=f"> [LINK]({transcript_link})",
                            color=Color.green(),
                        )

                        await channel.send(embed=embed)

                await interaction.channel.delete()

        self.add_item(
            CloseTicketButton(
                style=ButtonStyle.green,
                label=title,
                disabled=disabled,
                custom_id="ticket-close-button",
            )
        )


class ChoiceEmbedColor(ui.Select):
    def __init__(
        self,
        original_message: Message,
        embed: Embed,
    ) -> None:
        self.original_messaage: Message = original_message
        self.embed: Embed = embed

        self.colors: dict[str, Color] = {
            "red": Color.red(),
            "dark": Color.dark_theme(),
            "blue": Color.blue(),
            "yellow": Color.yellow(),
            "green": Color.green(),
            "orange": Color.orange(),
            "purple": Color.purple(),
        }

        options = [
            SelectOption(
                label="Czerwony",
                description="Czerwony kolor wiadomości",
                emoji="🔴",
                value="red",
            ),
            SelectOption(
                label="Ciemny",
                description="Ciemny kolor wiadomości",
                emoji="⚫",
                value="dark",
            ),
            SelectOption(
                label="Niebieski",
                description="Niebieski kolor wiadomości",
                emoji="🔵",
                value="blue",
            ),
            SelectOption(
                label="Fioletowy",
                description="Fioletowy kolor wiadomości",
                emoji="🟣",
                value="purple",
            ),
            SelectOption(
                label="Żółty",
                description="Żółty kolor wiadomości",
                emoji="🟡",
                value="yellow",
            ),
            SelectOption(
                label="Zielony",
                description="Zielony kolor wiadomości",
                emoji="🟢",
                value="green",
            ),
            SelectOption(
                label="Pomarańczony",
                description="Szary kolor wiadomości",
                emoji="🟠",
                value="orange",
            ),
        ]

        super().__init__(
            placeholder="Wybierz kolor",
            options=options,
        )

    async def callback(self, interaction: CustomInteraction):
        new_color: Color = self.colors[self.values[0]]
        self.embed.colour = new_color
        await self.original_messaage.edit(embed=self.embed)


class ChoiceColorEmbedView(ui.View):
    def __init__(self, message: Message, embed: Embed):
        super().__init__(timeout=None)

        self.add_item(ChoiceEmbedColor(message, embed))


class ConfigureTicketModal(ui.Modal):
    def __init__(
        self,
        message_to_edit: Message,
        embed_to_edit: Embed,
        title: bool = False,
        description: bool = False,
        button: bool = False,
    ):
        super().__init__(title="Konfiguracja wiadomości")

        self.embed_to_edit: Embed = embed_to_edit
        self.message_to_edit: Message = message_to_edit
        self._button: bool = False
        self._title: bool = False
        self._description: bool = False

        if button:
            self._button: bool = True
            self.input = ui.TextInput(
                label="Podaj tytuł przycisku",
                required=True,
                max_length=60,
                min_length=1,
            )
            self.add_item(self.input)

        if title:
            self._title: bool = True
            self.input = ui.TextInput(
                label="Podaj tytuł wiadomości",
                required=True,
                max_length=128,
                min_length=1,
            )
            self.add_item(self.input)

        if description:
            self._description: bool = True
            self.input = ui.TextInput(
                label="Podaj opis wiadomości",
                style=TextInputStyle.paragraph,
                required=False,
                max_length=2000,
            )
            self.add_item(self.input)

    async def callback(self, interaction: CustomInteraction):
        content: Optional[str] = self.input.value
        if not content:
            return

        if self._title:
            self.embed_to_edit.title = content
            await self.message_to_edit.edit(embed=self.embed_to_edit)

        if self._description:
            self.embed_to_edit.description = content
            await self.message_to_edit.edit(embed=self.embed_to_edit)

        if self._button:
            await self.message_to_edit.edit(view=PreviewButtonView(content))
            self.stop()


class PreviewButtonView(ui.View):
    def __init__(self, title: str, disabled: bool = True):  # pylint: disable=too-many-statements
        super().__init__(timeout=None)

        class PreviewButton(ui.Button):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            @staticmethod
            async def format_text(
                texts: tuple[str, ...],
                ticket_id: int,
                category: CategoryChannel,
                interaction: CustomInteraction,
            ) -> tuple[str, ...]:
                assert interaction.user

                (
                    embed_title,
                    embed_description,
                    embed_button,
                    embed_image,
                    embed_color,
                    roles,
                ) = texts

                embed_title = (
                    embed_title.replace(
                        "{ticket_id}",
                        str(ticket_id),
                    )
                    .replace(
                        "{ticket_category}",
                        category.name,
                    )
                    .replace(
                        "{ticket_author}",
                        str(interaction.user),
                    )
                    .replace(
                        "{ticket_author_mention}",
                        str(interaction.user.mention),
                    )
                    .replace(
                        "{ticket_author_id}",
                        str(interaction.user.id),
                    )
                )

                embed_description = (
                    embed_description.replace(
                        "{ticket_id}",
                        str(ticket_id),
                    )
                    .replace(
                        "{ticket_category}",
                        str(category.name),
                    )
                    .replace(
                        "{ticket_author}",
                        str(interaction.user),
                    )
                    .replace(
                        "{ticket_author_mention}",
                        str(interaction.user.mention),
                    )
                    .replace(
                        "{ticket_author_id}",
                        str(interaction.user.id),
                    )
                )

                return (
                    embed_title,
                    embed_description,
                    embed_color,
                    embed_image,
                    embed_button,
                    roles,
                )

            async def callback(
                self,
                interaction: CustomInteraction,
            ):  # pylint: disable=too-many-statements
                assert isinstance(interaction.user, Member) and interaction.guild

                if not interaction.message:
                    return await interaction.send_error_message(
                        description="Wystąpił nieoczekiwany błąd.",
                        ephemeral=True,
                    )

                await interaction.response.defer(ephemeral=True)
                bot: Smiffy = interaction.bot

                response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                    "SELECT * FROM tickets WHERE guild_id = ? AND message_id = ?",
                    (
                        interaction.guild_id,
                        interaction.message.id,
                    ),
                )
                if not response:
                    return await interaction.send_error_message(
                        description="Wystąpił błąd z danymi tego ticketu. "
                        "Upewnij się, że podana rola oraz kategoria nadal istnieje."
                    )

                category: Optional[GuildChannel] = await bot.cache.get_channel(
                    interaction.guild.id, response[2]
                )

                if not isinstance(category, CategoryChannel):
                    return await interaction.send_error_message(
                        description="Wystąpił błąd z danymi tego ticketu. "
                        "Upewnij się, że podana rola oraz kategoria nadal istnieje."
                    )

                roles_data: list[int] | int = literal_eval(response[4])

                if isinstance(roles_data, list):
                    roles: list[Role | None] = [
                        await bot.cache.get_role(
                            interaction.guild.id,
                            role,
                        )
                        for role in roles_data
                    ]
                else:
                    roles: list[Role | None] = [
                        await bot.cache.get_role(
                            interaction.guild.id,
                            roles_data,
                        )
                    ]

                ticket_id: int = response[5]
                name: str = response[3]

                channel: TextChannel = await interaction.guild.create_text_channel(
                    name=f"{name}-{ticket_id}",
                    category=category,
                )

                await channel.set_permissions(
                    interaction.guild.default_role,
                    view_channel=False,
                )
                for role in roles:
                    if role:
                        await channel.set_permissions(
                            role,
                            view_channel=True,
                            send_messages=True,
                        )

                await channel.set_permissions(
                    interaction.user,
                    view_channel=True,
                    send_messages=True,
                )

                for target in channel.overwrites:
                    if isinstance(target, Role):
                        for role in roles:
                            if role and target.id != role.id:
                                await channel.set_permissions(
                                    target,
                                    view_channel=False,
                                    send_messages=False,
                                )
                    else:
                        if interaction.user.id != target.id:
                            await channel.set_permissions(
                                target,
                                view_channel=False,
                                send_messages=False,
                            )

                ticket_id += 1
                await bot.db.execute_fetchone(
                    "UPDATE tickets SET ticket_id = ? WHERE guild_id = ? AND message_id = ?",
                    (
                        ticket_id,
                        interaction.guild.id,
                        interaction.message.id,
                    ),
                )

                response_ticket_close: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                    "SELECT * FROM tickets_close WHERE guild_id = ? AND channel_name = ?",
                    (interaction.guild.id, name),
                )

                if not response_ticket_close:
                    description: str = (
                        f"{Emojis.REPLY.value} Kategoria: `{name}`"
                        f"\n> Utworzono przez: `{interaction.user}`\n\n"
                        f"**Witaj {interaction.user.mention}, postaraj się opisać swój problem, "
                        f"a odpowiednie osoby niedługą odpiszą.**"
                    )

                    embed = Embed(
                        title=f"SmiffyBot Ticket - {ticket_id}#",
                        description=description,
                        color=Color.yellow(),
                        timestamp=utils.utcnow(),
                    )
                    embed.set_thumbnail(url=interaction.guild_icon_url)
                    embed.set_author(
                        name=interaction.user,
                        icon_url=interaction.user_avatar_url,
                    )
                    await channel.send(
                        embed=embed,
                        view=CloseTicketButtonView(disabled=False),
                    )
                else:
                    converted_values: tuple[str, ...] = await self.format_text(
                        response_ticket_close[2::],
                        ticket_id,
                        category,
                        interaction,
                    )

                    embed_title: str = converted_values[0]
                    embed_description: str = converted_values[1]
                    embed_color: str = converted_values[2]
                    embed_image: str = converted_values[3]
                    embed_button: str = converted_values[4]

                    embed = Embed(
                        title=embed_title,
                        description=embed_description,
                        color=int(
                            f"0x{embed_color.replace('#', '')}",
                            16,
                        ),
                        timestamp=utils.utcnow(),
                    )
                    if embed_image == "True":
                        embed.set_thumbnail(url=interaction.guild_icon_url)

                    await channel.send(
                        embed=embed,
                        view=CloseTicketButtonView(
                            title=embed_button,
                            disabled=False,
                        ),
                    )

                await channel.send(
                    f"{interaction.user.mention}",
                    delete_after=1,
                    allowed_mentions=AllowedMentions(
                        everyone=True,
                        users=True,
                        roles=True,
                    ),
                )

                try:
                    await channel.send(
                        f"{' '.join([role.mention for role in roles if role])}",
                        allowed_mentions=AllowedMentions(
                            everyone=True,
                            users=True,
                            roles=True,
                        ),
                        delete_after=1,
                    )
                except (
                    errors.HTTPException,
                    errors.Forbidden,
                ):
                    pass

                await interaction.followup.send(
                    f"Ticket: {channel.mention} został utworzony!",
                    ephemeral=True,
                )

        self.add_item(
            PreviewButton(
                style=ButtonStyle.green,
                label=title,
                disabled=disabled,
                custom_id="ticketbutton",
            )
        )


class AccessRoleSelect(ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="Wybierz role z dostępem do ticketów",
            custom_id="ticket-roles",
            max_values=10,
        )

    async def callback(self, interaction: CustomInteraction):
        assert isinstance(interaction.user, Member) and interaction.guild

        await interaction.response.defer(ephemeral=True)

        for role in self.values.roles:
            if interaction.user.id != interaction.guild.owner_id:
                if role.position >= interaction.user.top_role.position:
                    return await interaction.send_error_message(
                        description=f"Nie możesz użyć roli: `{role}`.\n> *Posiadasz zbyt małe uprawnienia*",
                        ephemeral=True,
                    )

            if not role.is_assignable():
                return await interaction.send_error_message(
                    description=f"Nie możesz użyć roli: `{role}`.\n> *Rola posiada większe uprawnienia od bota*",
                    ephemeral=True,
                )


class ButtonsCloseTicketView(ui.View):
    def __init__(
        self,
        preview_embed: Embed,
        preview_message: Message,
        author_id: int,
        first_instance: ButtonsView,
    ):
        super().__init__(timeout=None)

        self.first_instance: ButtonsView = first_instance
        self.preview_embed: Embed = preview_embed
        self.preview_message: Message = preview_message
        self.embed_image: bool = True

        self.button_title: str = "Zamknij ticket!"
        self.author_id: int = author_id

        self.role_close_select = SelectCloseRole()
        self.add_item(self.role_close_select)

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if self.author_id != interaction.user.id:
            await interaction.send_error_message(
                description="Tylko autor użytej komendy może tegu użyć.",
                ephemeral=True,
            )
            return False

        return True

    @ui.button(
        label="Edytuj Tytuł",
        style=ButtonStyle.gray,
        emoji="💥",
        row=1,
    )  # pyright: ignore
    async def title(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        modal = ConfigureTicketModal(
            message_to_edit=self.preview_message,
            embed_to_edit=self.preview_embed,
            title=True,
        )
        await interaction.response.send_modal(modal)

    @ui.button(
        label="Edytuj Opis",
        style=ButtonStyle.gray,
        emoji="📃",
        row=1,
    )  # pyright: ignore
    async def description(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        modal = ConfigureTicketModal(
            message_to_edit=self.preview_message,
            embed_to_edit=self.preview_embed,
            description=True,
        )
        await interaction.response.send_modal(modal)

    @ui.button(
        label="Edytuj Kolor",
        style=ButtonStyle.gray,
        emoji="🌀",
        row=1,
    )  # pyright: ignore
    async def color(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        view = ChoiceColorEmbedView(
            self.preview_message,
            self.preview_embed,
        )

        embed = Embed(
            title="`🔶` Wybierz kolor, który chcesz ustawić",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Wybierz kolor embedu.",
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        await interaction.send(embed=embed, view=view, ephemeral=True)

    @ui.button(
        label="Obraz serwera (on/off)",
        style=ButtonStyle.gray,
        emoji="📷",
        row=1,
    )  # pyright: ignore
    async def picture(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        if not self.preview_embed.thumbnail.url:
            self.embed_image = True
            self.preview_embed.set_thumbnail(url=interaction.guild_icon_url)
        else:
            self.embed_image = False
            self.preview_embed.set_thumbnail(url=None)

        await self.preview_message.edit(embed=self.preview_embed)

    @ui.button(
        label="Edytuj Przycisk",
        style=ButtonStyle.gray,
        emoji="🔗",
        row=1,
    )  # pyright: ignore
    async def button(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        modal = ConfigureTicketModal(
            message_to_edit=self.preview_message,
            embed_to_edit=self.preview_embed,
            button=True,
        )

        await interaction.response.send_modal(modal)
        if not await modal.wait() and modal.input.value:
            self.button_title = modal.input.value

    @ui.button(
        label="Zakończ",
        style=ButtonStyle.green,
        emoji="✅",
        row=2,
    )  # pyright: ignore
    async def end(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild and isinstance(interaction.user, Member)

        await interaction.response.defer(ephemeral=True)

        bot: Smiffy = interaction.bot
        transcript_channel: Optional[int] = None

        if self.first_instance.transcript_channel:
            transcript_channel = self.first_instance.transcript_channel.id

        for role in self.role_close_select.values.roles:
            if interaction.user.id != interaction.guild.owner_id:
                if role.position >= interaction.user.top_role.position:
                    await interaction.send_error_message(
                        description=f"Nie możesz użyć roli: `{role}`.\n> *Posiadasz zbyt małe uprawnienia*",
                        ephemeral=True,
                    )
                    return

            if not role.is_assignable():
                await interaction.send_error_message(
                    description=f"Nie możesz użyć roli: `{role}`.\n> *Rola posiada większe uprawnienia od bota*",
                    ephemeral=True,
                )
                return

        roles: list[int] = []
        roles_close: list[int] = []

        for role in self.first_instance.role_select.values:
            roles.append(role.id)

        if self.role_close_select.values.roles:
            for role in self.role_close_select.values:
                roles_close.append(role.id)

        await bot.db.execute_fetchone(
            "INSERT INTO tickets(guild_id, message_id, category_id, channel_name, roles_id, ticket_id, "
            "transcript_channel) VALUES(?,?,?,?,?,?,?)",
            (
                interaction.guild.id,
                self.first_instance.preview_message.id,
                self.first_instance.category.id,
                self.first_instance.channel_name.lower(),
                str(roles),
                0,
                transcript_channel,
            ),
        )

        await bot.db.execute_fetchone(
            "INSERT INTO tickets_close(guild_id, channel_name, message_title, message_description, "
            "message_button, message_image, message_color, ticket_close_roles) VALUES(?,?,?,?,?,?,?,?)",
            (
                interaction.guild.id,
                self.first_instance.channel_name.lower(),
                self.preview_embed.title,
                self.preview_embed.description,
                self.button_title,
                str(self.embed_image),
                str(self.preview_embed.color),
                str(roles_close),
            ),
        )

        if interaction.message:
            await interaction.message.delete()

        await interaction.send_success_message(
            title=f"Instalacja ticketów zakończona {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Ten kanał możesz już usunąć. "
            f"Przycisk do tworzenia ticketów został włączony.",
            ephemeral=True,
        )

        new_view = PreviewButtonView(
            title=self.first_instance.button_title,
            disabled=False,
        )
        await self.first_instance.preview_message.edit(
            embed=self.first_instance.preview_embed,
            view=new_view,
        )
        await self.preview_message.delete()


class ButtonsView(ui.View):
    def __init__(
        self,
        preview_embed: Embed,
        preview_message: Message,
        other_options: tuple[
            CategoryChannel,
            str,
            Optional[TextChannel],
        ],
        author_id: int,
    ):
        super().__init__(timeout=None)

        self.preview_embed: Embed = preview_embed
        self.preview_message: Message = preview_message

        self.transcript_channel: Optional[TextChannel] = other_options[2]
        self.channel_name: str = other_options[1]
        self.category: CategoryChannel = other_options[0]

        self.button_title: str = "Stwórz ticket!"
        self.author_id: int = author_id

        self.role_select = AccessRoleSelect()
        self.add_item(self.role_select)

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if self.author_id != interaction.user.id:
            await interaction.send_error_message(
                description="Tylko autor użytej komendy może tegu użyć.",
                ephemeral=True,
            )
            return False

        return True

    @ui.button(
        label="Tytuł",
        style=ButtonStyle.gray,
        emoji="💥",
        row=1,
    )  # pyright: ignore
    async def title(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        modal = ConfigureTicketModal(
            message_to_edit=self.preview_message,
            embed_to_edit=self.preview_embed,
            title=True,
        )
        await interaction.response.send_modal(modal)

    @ui.button(
        label="Opis",
        style=ButtonStyle.gray,
        emoji="📃",
        row=1,
    )  # pyright: ignore
    async def description(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        modal = ConfigureTicketModal(
            message_to_edit=self.preview_message,
            embed_to_edit=self.preview_embed,
            description=True,
        )
        await interaction.response.send_modal(modal)

    @ui.button(
        label="Kolor",
        style=ButtonStyle.gray,
        emoji="🌀",
        row=1,
    )  # pyright: ignore
    async def color(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        view = ChoiceColorEmbedView(
            self.preview_message,
            self.preview_embed,
        )

        embed = Embed(
            title="`🔶` Wybierz kolor, który chcesz ustawić",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Wybierz kolor embedu.",
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        await interaction.send(embed=embed, view=view, ephemeral=True)

    @ui.button(
        label="Obraz serwera (on/off)",
        style=ButtonStyle.gray,
        emoji="📷",
        row=1,
    )  # pyright: ignore
    async def picture(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        if not self.preview_embed.thumbnail.url:
            self.preview_embed.set_thumbnail(url=interaction.guild_icon_url)
        else:
            self.preview_embed.set_thumbnail(url=None)
        await self.preview_message.edit(embed=self.preview_embed)

    @ui.button(
        label="Przycisk",
        style=ButtonStyle.gray,
        emoji="🔗",
        row=1,
    )  # pyright: ignore
    async def button(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        modal = ConfigureTicketModal(
            message_to_edit=self.preview_message,
            embed_to_edit=self.preview_embed,
            button=True,
        )
        await interaction.response.send_modal(modal)
        if not await modal.wait() and modal.input.value:
            self.button_title = modal.input.value

    @ui.button(
        label="Zakończ",
        style=ButtonStyle.green,
        emoji="✅",
        row=2,
    )  # pyright: ignore
    async def end(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert isinstance(interaction.user, Member) and interaction.guild

        if not interaction.message:
            await interaction.send_error_message(
                description="Wystąpił nieoczekiwany błąd.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        if len(self.role_select.values.roles) == 0:
            await interaction.send_error_message(
                description="Wybierz co najmniej jedną role z dostępem do ticketów",
                ephemeral=True,
            )
            return

        for role in self.role_select.values.roles:
            if interaction.user.id != interaction.guild.owner_id:
                if role.position >= interaction.user.top_role.position:
                    await interaction.send_error_message(
                        description=f"Nie możesz użyć roli: `{role}`.\n> *Posiadasz zbyt małe uprawnienia*",
                        ephemeral=True,
                    )
                    return

            if not role.is_assignable():
                await interaction.send_error_message(
                    description=f"Nie możesz użyć roli: `{role}`.\n> *Rola posiada większe uprawnienia od bota*",
                    ephemeral=True,
                )
                return

        _ext_channel: TextChannel = await interaction.guild.create_text_channel(
            name=f"{self.channel_name}-konfiguracja",
            category=self.category,
        )

        await _ext_channel.set_permissions(
            interaction.guild.default_role,
            view_channel=False,
        )
        await _ext_channel.set_permissions(interaction.user, view_channel=True)

        for permission in _ext_channel.overwrites:
            if not isinstance(permission, Role) and permission.id == interaction.user.id:
                continue

            await _ext_channel.set_permissions(
                permission,
                view_channel=False,
                send_messages=False,
            )

        await _ext_channel.send(
            f"{interaction.user.mention}",
            allowed_mentions=AllowedMentions(users=True),
            delete_after=1,
        )

        embed = Embed(
            title=f"Połowa sukcesu! {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            description=f"Teraz przejdź na utworzony kanał: {_ext_channel.mention} i dokończ instalacje.",
        )
        await interaction.message.edit(embed=embed, view=None)

        preview_embed = Embed(
            title="SmiffyBot Ticket - {ticket_id}#",
            description="Przykładowy opis.",
            color=Color.yellow(),
            timestamp=utils.utcnow(),
        )
        preview_embed.set_thumbnail(url=interaction.guild_icon_url)
        preview_embed.set_author(name="Podgląd wyglądu wiadomości")

        try:
            preview_message: Message = await _ext_channel.send(
                embed=preview_embed,
                view=CloseTicketButtonView(),
            )
        except (
            errors.HTTPException,
            errors.Forbidden,
        ):
            await interaction.send_error_message(description="Wystąpił błąd podczas wysyłania wiadomości.")
            return

        variables: str = """\n```
{ticket_id} - ID stworzonego ticketu

{ticket_category} - Nazwa kategorii kanału ticketu

{ticket_author} - Nazwa + Hasztag osoby, która utworzyła ticket

{ticket_author_mention} - Oznaczenie osoby, która utworzyła ticket

{ticket_author_id} - ID osoby, która utworzyła ticket
```
`❌` **Ważne**
- Jeśli użyjesz dostępnych zmiennych, będą one widoczne dopiero po zakończeniu instalacji i stworzeniu nowego ticketu.

- Zmienne działają tylko dla tytułu i opisu.

- Role z dostępem do zamykania ticketów to opcjonalna opcja. \
Jeśli chcesz, aby każdy z dostępem do kanału mógł to zrobić - zostaw liste pustą.

- Bez względu na ustawione role do zamykania ticketów, właściciel zawsze ma dostęp do zamknięcia ticketu.
"""

        embed = Embed(
            title="<a:utility:1008513934233444372> Konfigurowanie systemu ticketów",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description="> W drugim kroku skonfiguruj wygląd wiadomości od zamykania ticketu.\n\n"
            "**Wybierz opcję, którą chcesz zmienić. Po zakończeniu naciśnij przycisk `Zakończ`**"
            "\n\n`🛠️` **Dostępne Zmienne:**" + variables,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        configurebuttons = ButtonsCloseTicketView(
            preview_embed=preview_embed,
            preview_message=preview_message,
            author_id=interaction.user.id,
            first_instance=self,
        )

        await _ext_channel.send(embed=embed, view=configurebuttons)


class CommandTickets(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot)

        self.bot.loop.create_task(self.update_views())

    async def update_views(self):
        self.bot.add_view(
            PreviewButtonView(
                title="Stwórz ticket!",
                disabled=False,
            )
        )
        self.bot.add_view(CloseTicketButtonView())

    @slash_command(
        name="tickety",
        description="Komenda dotycząca ticketów",
        dm_permission=False,
    )
    async def tickets(self, interaction: CustomInteraction) -> None:
        pass

    @tickets.subcommand(  # pyright: ignore
        name="instalacja",
        description="Rozpocznyna instalacje ticketów na serwerze!",
    )
    @PermissionHandler(manage_guild=True)
    async def tickets_setup(
        self,
        interaction: CustomInteraction,
        category: CategoryChannel = SlashOption(
            name="kategoria",
            description="Kategoria do ticketów",
        ),
        channel_name: str = SlashOption(
            name="nazwa_kanału",
            description="Podaj nazwę kanałów do ticketów",
            max_length=24,
            min_length=2,
        ),
        transcript_channel: Optional[TextChannel] = SlashOption(
            name="zapis_ticketow",
            description="Podaj kanał na którym chcesz zapis ticketów",
        ),
    ):
        assert isinstance(interaction.user, Member) and interaction.guild

        if not isinstance(
            interaction.channel,
            (TextChannel, Thread),
        ):
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        await interaction.response.defer()

        if "-" in channel_name.lower():
            return await interaction.send_error_message(
                description="Znak `-` jest zakazany w argumencie `nazwa_kanału`"
            )

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM tickets WHERE guild_id = ? AND channel_name = ?",
            (
                interaction.guild.id,
                channel_name.lower(),
            ),
        )
        if response:
            return await interaction.send_error_message(
                f"Już istnieje system ticketów z nazwą kanału: `{channel_name}`"
            )

        preview_embed = Embed(
            color=Color.dark_theme(),
            title="Podgląd wyglądu ticketów",
        )
        preview_button = PreviewButtonView("Stwórz ticket!")
        preview_message: Message = await interaction.channel.send(
            embed=preview_embed,
            view=preview_button,
        )

        embed = Embed(
            title="<a:utility:1008513934233444372> Konfigurowanie systemu ticketów",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} W pierwszym kroku skonfiguruj wygląd wiadomości od tworzenia ticketów."
            f"\n\n- Wybierz opcję, którą chcesz zmienić.\n"
            f"- Po zakończeniu naciśnij przycisk `Zakończ`",
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        configure_buttons = ButtonsView(
            preview_message=preview_message,
            preview_embed=preview_embed,
            other_options=(
                category,
                channel_name,
                transcript_channel,
            ),
            author_id=interaction.user.id,
        )

        await interaction.send(embed=embed, view=configure_buttons)

    @tickets.subcommand(
        name="usuń",
        description="Usuwa system ticketu z serwera.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def ticket_delete(
        self,
        interaction: CustomInteraction,
        channel_name: str = SlashOption(
            name="nazwa",
            description="Podaj nazwę kanału",
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM tickets WHERE guild_id = ? AND channel_name = ?",
            (interaction.guild.id, channel_name),
        )
        if not response:
            return await interaction.send_error_message(
                description=f"Niestety, ale nie odnalazłem systemu ticketów o nazwie kanału: `{channel_name}`"
            )

        await interaction.response.defer()

        message: Optional[Message] = await MessageConverter().convert(interaction, str(response[1]))
        if message:
            await message.delete()

        await self.bot.db.execute_fetchone(
            "DELETE FROM tickets WHERE guild_id = ? AND channel_name = ?",
            (interaction.guild.id, channel_name),
        )

        await self.bot.db.execute_fetchone(
            "DELETE FROM tickets_close WHERE guild_id = ? AND channel_name = ?",
            (interaction.guild.id, channel_name),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie usunięto ticket {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Ticket powiązany z nazwą kanału: `{channel_name}` został usunięty.",
        )

    @ticket_delete.on_autocomplete("channel_name")
    async def ticket_delete_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ):
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM tickets WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return

        channel_name_data: list[str] = []
        for data in response:
            channel_name_data.append(data[3])

        if not query:
            return channel_name_data[0:25]

        get_near_channel_name: list[str] = [
            name for name in channel_name_data if name.lower().startswith(query.lower())
        ]
        return get_near_channel_name

    @tickets.subcommand(  # pyright: ignore
        name="info",
        description="Pokazuje wszystkie dostępne informacje o tickecie.",
    )
    @PermissionHandler(manage_guild=True)
    async def ticket_info(
        self,
        interaction: CustomInteraction,
        channel_name: str = SlashOption(
            name="nazwa",
            description="Podaj nazwę kanału",
        ),
    ):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM tickets WHERE guild_id = ? AND channel_name = ?",
            (interaction.guild.id, channel_name),
        )

        response_close: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM tickets_close WHERE guild_id = ? AND channel_name = ?",
            (interaction.guild.id, channel_name),
        )
        if not response:
            return await interaction.send_error_message(
                description=f"Niestety, ale nie odnalazłem systemu ticketów o nazwie kanału: `{channel_name}`"
            )

        await interaction.response.defer()

        category: Optional[GuildChannel] = await self.bot.cache.get_channel(interaction.guild.id, response[2])

        if not isinstance(category, CategoryChannel):
            return await interaction.send_error_message(
                description="Kategoria tego systemu ticketów nie istnieje."
            )

        ticket_id: str = response[5]

        roles: list[str] = []
        roles_close: list[str] = []

        for role_id in literal_eval(response[4]):
            role: Optional[Role] = await self.bot.cache.get_role(interaction.guild.id, role_id)
            if role:
                roles.append(role.mention)

        if response_close and response_close[7]:
            for role_id in literal_eval(response_close[7]):
                role: Optional[Role] = await self.bot.cache.get_role(interaction.guild.id, role_id)

                if role:
                    roles_close.append(role.mention)

        message: Optional[Message] = await MessageConverter().convert(interaction, str(response[1]))

        _description: str = f"""
> `⚙️` Kategoria: {category.mention}

> `📌` Nazwa Kanału: `{channel_name}`

> `🔍` Ticket ID: `{ticket_id}`
"""
        if message:
            _description += f"\n> `🔑` Wiadomość Ticketu: [`LINK`]({message.jump_url})\n"

        if roles:
            _description += f"\n> `✨` Role dostępu: {' '.join(roles)}\n"

        if roles_close:
            _description += f"\n> `🌟` Role dostępu do zamykania: {' '.join(roles_close)}"

        embed = Embed(
            title="Informacje o ticketcie",
            color=Color.green(),
            description=_description,
            timestamp=utils.utcnow(),
        )

        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        await interaction.send(embed=embed)

    @ticket_info.on_autocomplete("channel_name")
    async def ticket_info_autocomplete(
        self,
        interaction: CustomInteraction,
        query: Optional[str],
    ):
        assert interaction.guild

        response: Iterable[DB_RESPONSE] = await self.bot.db.execute_fetchall(
            "SELECT * FROM tickets WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return

        channel_name_data: list[str] = []
        for data in response:
            channel_name_data.append(data[3])

        if not query:
            return channel_name_data[0:25]

        get_near_channel_name: list[str] = [
            name for name in channel_name_data if name.lower().startswith(query.lower())
        ]
        return get_near_channel_name


def setup(bot: Smiffy):
    bot.add_cog(CommandTickets(bot))
