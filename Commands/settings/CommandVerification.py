from __future__ import annotations

from random import choice
from string import ascii_lowercase
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from captcha.image import ImageCaptcha
from nextcord import (
    ButtonStyle,
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

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from nextcord import Guild

    from bot import Smiffy
    from typings import DB_RESPONSE


class CustomButton(ui.Button):
    def __init__(
        self,
        custom_callback: Callable[[dict], Awaitable[None]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self.custom_callback: Callable[[dict], Awaitable[None]] = custom_callback  # pyright: ignore

        self.button_code: str = kwargs["label"]

    async def callback(self, interaction: CustomInteraction) -> None:
        args: dict[str, Any] = {
            "button_code": self.button_code,
            "interaction": interaction,
        }
        await self.custom_callback(args)


class CaptchaButtons(ui.View):
    def __init__(self, captcha_code: str, message_id: int):
        super().__init__(timeout=None)

        self.captcha_code: str = captcha_code
        self.message_id: int = message_id

        self.add_item(
            CustomButton(
                custom_callback=self.button_callback,
                style=ButtonStyle.gray,
                label=self.captcha_code,
            )
        )

        for code in self.generate_random_codes(2):
            self.add_item(
                CustomButton(
                    custom_callback=self.button_callback,
                    style=ButtonStyle.gray,
                    label=code,
                )
            )

    @staticmethod
    async def get_verify_role(bot: Smiffy, guild: Guild, message_id: int) -> Optional[Role]:
        response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
            "SELECT role_id FROM verifications WHERE guild_id = ? AND message_id = ?",
            (guild.id, message_id),
        )
        if not response or not response[0]:
            return None

        role: Optional[Role] = await bot.cache.get_role(guild.id, response[0])
        return role

    @staticmethod
    def generate_random_codes(
        amount: int,
    ) -> list[str]:
        codes: list[str] = []

        for _ in range(amount):
            captcha_text: str = ""
            for code in range(8):  # pylint: disable=unused-variable
                captcha_text += choice(list(ascii_lowercase))

            codes.append(captcha_text)

        return codes

    async def button_callback(
        self,
        args: dict[str, CustomInteraction | str],
    ) -> None:
        interaction = args["interaction"]
        button_code = args["button_code"]

        assert isinstance(interaction, CustomInteraction) and isinstance(button_code, str)
        assert interaction.guild and isinstance(interaction.user, Member)

        if button_code != self.captcha_code:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                description=f"{Emojis.REPLY.value} Wcisnąłeś/aś nieprawidłowy przycisk. Spróbuj ponownie.",
                color=Color.red(),
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            await interaction.response.edit_message(
                embed=embed,
                content="",
                attachments=[],
                view=None,
            )
            return

        role: Optional[Role] = await self.get_verify_role(
            bot=interaction.bot,
            guild=interaction.guild,
            message_id=self.message_id,
        )
        if not role:
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                description=f"{Emojis.REDBUTTON.value} Rola po weryfikacji nie została znaleziona. "
                f"Skontaktuj się z administracją serwera.",
                color=Color.red(),
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            await interaction.response.edit_message(
                embed=embed,
                content="",
                attachments=[],
                view=None,
            )
            return

        try:
            await interaction.user.add_roles(role)
        except (
            errors.Forbidden,
            errors.HTTPException,
        ):
            embed = Embed(
                title=f"{Emojis.REDBUTTON.value} Wystąpił błąd.",
                description=f"{Emojis.REDBUTTON.value} Bot nie ma wystarczających uprawnień, aby nadać role "
                f"weryfikacji. Skontaktuj się z administracją serwera.",
                color=Color.red(),
                timestamp=utils.utcnow(),
            )
            embed.set_author(
                name=interaction.user,
                icon_url=interaction.user_avatar_url,
            )
            embed.set_thumbnail(url=interaction.guild_icon_url)
            await interaction.response.edit_message(
                embed=embed,
                content="",
                attachments=[],
                view=None,
            )
            return

        embed = Embed(
            title=f"Pomyślnie zweryfikowano {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Twoja weryfikacja przebiegła pomyślnie.",
            color=Color.green(),
            timestamp=utils.utcnow(),
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        await interaction.response.edit_message(
            embed=embed,
            content="",
            attachments=[],
            view=None,
        )


class ButtonVerifyView(ui.View):
    def __init__(self, title: str, disabled: bool = True):
        super().__init__(timeout=None)

        class ButtonVerify(ui.Button):
            @staticmethod
            async def get_verify_role(
                bot: Smiffy,
                guild: Guild,
                role_id: int,
            ) -> Optional[Role]:
                role: Optional[Role] = await bot.cache.get_role(guild.id, role_id)
                return role

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            async def callback(
                self,
                interaction: CustomInteraction,
            ):
                assert interaction.guild and isinstance(interaction.user, Member)

                if not interaction.message:
                    return await interaction.send_error_message(
                        description="Wystąpił nieoczekiwany błąd.",
                        ephemeral=True,
                    )

                await interaction.response.defer(ephemeral=True)
                bot: Smiffy = interaction.bot

                response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                    "SELECT * FROM verifications WHERE guild_id = ? AND message_id = ?",
                    (
                        interaction.guild.id,
                        interaction.message.id,
                    ),
                )
                if not response:
                    return await interaction.send_error_message(
                        description="Wystąpił błąd z danymi tej weryfikacji.",
                        ephemeral=True,
                    )

                role: Optional[Role] = await bot.cache.get_role(
                    guild_id=interaction.guild.id,
                    role_id=response[2],
                )
                if not role:
                    return await interaction.send_error_message(
                        description="Rola po weryfikacji nie została odnaleziona. Być może została usunięta. "
                        "\n**Skontaktuj się z administracją serwera.**",
                        ephemeral=True,
                    )

                if response[3] == "button":
                    try:
                        await interaction.user.add_roles(role)
                    except (
                        errors.Forbidden,
                        errors.HTTPException,
                    ):
                        return await interaction.send_error_message(
                            description="Bot nie posiada wymaganych permisji, aby nadać role weryfikacji. "
                            "Skontaktuj się z administracją serwera."
                        )
                    await interaction.send_success_message(
                        title=f"Pomyślnie zweryfikowano {Emojis.GREENBUTTON.value}",
                        description=f"{Emojis.REPLY.value} Twoja weryfikacja przebiegła pomyślnie.",
                        ephemeral=True,
                    )
                    return

                image = ImageCaptcha(width=300, height=100)

                captcha_text: str = ""
                for x in range(8):  # pylint: disable=unused-variable
                    captcha_text += choice(list(ascii_lowercase))

                data = image.generate(captcha_text)
                file = File(data, filename="captcha.png")

                embed = Embed(
                    title=f"Weryfikacja {Emojis.GREENBUTTON.value}",
                    timestamp=utils.utcnow(),
                    description=f"{Emojis.REPLY.value} Naciśnij odpowiedni przycisk z prawidłowym kodem.",
                    colour=Color.dark_theme(),
                )
                embed.set_image(url="attachment://captcha.png")
                buttons = CaptchaButtons(
                    captcha_text,
                    interaction.message.id,
                )

                await interaction.send(
                    embed=embed,
                    file=file,
                    ephemeral=True,
                    view=buttons,
                )

        self.add_item(
            ButtonVerify(
                style=ButtonStyle.green,
                label=title,
                disabled=disabled,
                custom_id="veryfibutton",
            )
        )


class ChoiceColorEmbed(ui.Select):
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
        self.add_item(ChoiceColorEmbed(message, embed))


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
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        if self._title:
            self.embed_to_edit.title = content
            await self.message_to_edit.edit(embed=self.embed_to_edit)

        if self._description:
            self.embed_to_edit.description = content
            await self.message_to_edit.edit(embed=self.embed_to_edit)

        if self._button:
            button_view = ButtonVerifyView(content)
            await self.message_to_edit.edit(view=button_view)
            self.stop()


class ConfigureButtonsView(ui.View):
    def __init__(
        self,
        preview_embed: Embed,
        preview_message: Message,
        options: tuple[Role, str, int],
    ):
        super().__init__(timeout=None)

        self.preview_embed: Embed = preview_embed
        self.preview_message: Message = preview_message

        self.role_access: Role = options[0]
        self.option: str = options[1]
        self.author_id: int = options[2]

        self.button_title: str = "Zweryfikuj!"

    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user

        if self.author_id != interaction.user.id:
            await interaction.send_error_message(
                description="Tylko autor użytej komendy może tego użyć.",
                ephemeral=True,
            )
            return False
        return True

    @ui.button(
        label="Tytuł",
        style=ButtonStyle.gray,
        emoji="✏️",
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
            description=f"{Emojis.REPLY.value} Wybierz kolor wiadomości.",
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
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

    @ui.button(  # pyright: ignore
        label="Zakończ",
        style=ButtonStyle.green,
        emoji=Emojis.GREENBUTTON.value,
        row=2,
    )
    async def end(
        self,
        button: ui.Button,  # pylint: disable=unused-argument
        interaction: CustomInteraction,
    ) -> None:
        assert interaction.guild

        bot: Smiffy = interaction.bot

        await bot.db.execute_fetchone(
            "INSERT INTO verifications(guild_id, message_id, role_id, type) VALUES(?,?,?,?)",
            (
                interaction.guild.id,
                self.preview_message.id,
                self.role_access.id,
                str(self.option),
            ),
        )
        new_view = ButtonVerifyView(
            title=self.button_title,
            disabled=False,
        )

        embed = Embed(
            title=f"Instalacja zakończona {Emojis.GREENBUTTON.value}",
            color=Color.green(),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Instalacja przebiegła pomyślnie.",
        )
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)

        if interaction.message:
            await interaction.message.edit(embed=embed, view=None)

        await self.preview_message.edit(
            embed=self.preview_embed,
            view=new_view,
        )


class CommandVerification(CustomCog):
    def __init__(self, bot: Smiffy) -> None:
        super().__init__(bot)

        self.bot.loop.create_task(self.update_views())

    async def update_views(self):
        self.bot.add_view(
            ButtonVerifyView(
                title="Weryfikacja!",
                disabled=False,
            )
        )

    @slash_command(name="weryfikacja", dm_permission=False)
    async def verify(self, interaction: CustomInteraction):
        pass

    @verify.subcommand(
        name="instalacja",
        description="Ustaw weryfikacje na serwerze!",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def verify_setup(
        self,
        interaction: CustomInteraction,
        role: Role = SlashOption(
            name="rola",
            description="Podaj rolę która ma być nadawana po weryfikacji.",
        ),
        option: str = SlashOption(
            name="typ_weryfikacji",
            description="Wybierz typ weryfikacji",
            choices={
                "Tylko przycisk": "button",
                "Przycisk + Kod Captcha": "captcha",
            },
        ),
    ):
        assert interaction.user and interaction.guild
        assert isinstance(
            interaction.channel,
            (TextChannel, Thread),
        )

        if not role.is_assignable() or role.is_premium_subscriber():
            return await interaction.send_error_message(
                description="Podana rola nie może zostac użyta lub ma większe uprawnienia od bota.",
                ephemeral=True,
            )

        await interaction.response.defer()

        preview_embed = Embed(
            title="<a:success:984490514332139600> Weryfikacja",
            color=Color.from_rgb(98, 231, 133),
            timestamp=utils.utcnow(),
            description=f"{Emojis.REPLY.value} Naciśnij przycisk poniżej, aby się zweryfikować.",
        )
        preview_embed.set_footer(text="Made by SmiffyBot!")
        preview_embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild_icon_url,
        )
        verifybutton = ButtonVerifyView(title="Zweryfikuj")

        preview_message: Message = await interaction.channel.send(
            embed=preview_embed,
            view=verifybutton,
        )

        await interaction.channel.send(
            f"{interaction.user.mention}",
            delete_after=1,
        )

        embed = Embed(
            title="<a:utility:1008513934233444372> Konfigurowanie wiadomości weryfikacji",
            color=Color.dark_theme(),
            timestamp=utils.utcnow(),
            description="- Wybierz opcję, którą chcesz zmienić.\n- Po zakończeniu naciśnij przycisk `Zakończ`",
        )
        embed.set_thumbnail(url=interaction.guild_icon_url)
        configure_buttons = ConfigureButtonsView(
            preview_embed,
            preview_message,
            (role, option, interaction.user.id),
        )
        await interaction.send(embed=embed, view=configure_buttons)


def setup(bot: Smiffy):
    bot.add_cog(CommandVerification(bot))
