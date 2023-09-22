# pylint: disable=unused-argument

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from easy_pil import Editor, Font, load_image_async
from easy_pil.canvas import Image
from nextcord import (
    ButtonStyle,
    Color,
    Embed,
    File,
    Member,
    SlashOption,
    TextChannel,
    slash_command,
    ui,
    utils,
)

from enums import Emojis
from utilities import CustomCog, CustomInteraction, PermissionHandler

if TYPE_CHECKING:
    from bot import Smiffy
    from utilities import DB_RESPONSE


class EditModal(ui.Modal):
    def __init__(
        self,
        placeholder_text: str,
        main_text: bool = False,
        first_text: bool = False,
        second_text: bool = False,
        title: str = "Edytuj tekst przywitania",
    ):
        super().__init__(title)

        if main_text:
            self.input = ui.TextInput(
                label="Podaj główny tekst",
                required=True,
                max_length=35,
                min_length=1,
                placeholder=placeholder_text,
            )

        if first_text:
            self.input = ui.TextInput(
                label="Podaj pierwszy tekst",
                required=True,
                max_length=45,
                min_length=1,
                placeholder=placeholder_text,
            )

        if second_text:
            self.input = ui.TextInput(
                label="Podaj drugi tekst",
                required=True,
                max_length=55,
                min_length=1,
                placeholder=placeholder_text,
            )
        self.add_item(self.input)

    async def callback(self, interaction: CustomInteraction):
        await interaction.response.send_message(
            "Edytowanie podglądu...",
            ephemeral=True,
        )
        self.stop()


class EditButtons(ui.View):
    async def interaction_check(self, interaction: CustomInteraction) -> bool:
        assert interaction.user and self.interaction.user

        if interaction.user.id != self.interaction.user.id:
            await interaction.send_error_message(
                description="Tylko autor użytej komendy może tego użyć.",
                ephemeral=True,
            )

            return False
        return True

    def __init__(
        self,
        embed: Embed,
        interaction: CustomInteraction,
        channel_id: int,
        goodbye: bool = False,
    ):
        super().__init__(timeout=None)

        self.embed: Embed = embed
        self.interaction: CustomInteraction = interaction
        self.channel_id: int = channel_id

        self.goodbye: bool = goodbye
        self.main_text: str = "Glowny tekst"
        self.first_text: str = "Pierwszy tekst"
        self.second_text: str = "Drugi tekst"

    @ui.button(
        label="Główny tekst",
        style=ButtonStyle.grey,
    )  # pyright: ignore
    async def main_title(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        if self.goodbye:
            modal = EditModal(
                placeholder_text=self.main_text,
                main_text=True,
                title="Edytuj tekst pożegnania",
            )
        else:
            modal = EditModal(
                placeholder_text=self.main_text,
                main_text=True,
            )

        await interaction.response.send_modal(modal)

        if not await modal.wait() and modal.input.value:
            self.main_text = modal.input.value

            image = await self.update_image()
            if not self.goodbye:
                self.embed.set_image("attachment://welcomecard.jpg")
            else:
                self.embed.set_image("attachment://goodbyecard.jpg")

            if interaction.message:
                await interaction.message.edit(embed=self.embed, file=image)

    @ui.button(
        label="Pierwszy tekst",
        style=ButtonStyle.grey,
    )  # pyright: ignore
    async def first_title(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        if self.goodbye:
            modal = EditModal(
                placeholder_text=self.main_text,
                first_text=True,
                title="Edytuj tekst pożegnania",
            )
        else:
            modal = EditModal(
                placeholder_text=self.main_text,
                first_text=True,
            )

        await interaction.response.send_modal(modal)

        if not await modal.wait() and modal.input.value:
            self.first_text = modal.input.value

            image = await self.update_image()
            if not self.goodbye:
                self.embed.set_image("attachment://welcomecard.jpg")
            else:
                self.embed.set_image("attachment://goodbyecard.jpg")

            if interaction.message:
                await interaction.message.edit(embed=self.embed, file=image)

    @ui.button(
        label="Drugi tekst",
        style=ButtonStyle.grey,
    )  # pyright: ignore
    async def second_title(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):  # pylint: disable=unused-argument
        if self.goodbye:
            modal = EditModal(
                placeholder_text=self.main_text,
                second_text=True,
                title="Edytuj tekst pożegnania",
            )
        else:
            modal = EditModal(
                placeholder_text=self.main_text,
                second_text=True,
            )

        await interaction.response.send_modal(modal)

        if not await modal.wait() and modal.input.value:
            self.second_text = modal.input.value

            image = await self.update_image()
            if not self.goodbye:
                self.embed.set_image("attachment://welcomecard.jpg")
            else:
                self.embed.set_image("attachment://goodbyecard.jpg")

            if interaction.message:
                await interaction.message.edit(embed=self.embed, file=image)

    @ui.button(  # pyright: ignore
        label="Zakończ",
        style=ButtonStyle.green,
        emoji=Emojis.GREENBUTTON.value,
        row=2,
    )
    async def end(
        self,
        button: ui.Button,
        interaction: CustomInteraction,
    ):
        assert interaction.guild

        if not interaction.message:
            return await interaction.send_error_message(description="Wystąpił nieoczekiwany błąd.")

        await interaction.response.defer()

        bot: Smiffy = interaction.bot
        if not self.goodbye:
            response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT * FROM welcomes WHERE guild_id = ?",
                (interaction.guild.id,),
            )
            if response:
                return await interaction.send_error_message(
                    description="Niestety, ale przywitania już są ustawione."
                )

            data: tuple[str, ...] = (
                self.main_text,
                self.first_text,
                self.second_text,
            )

            await bot.db.execute_fetchone(
                "INSERT INTO welcomes(guild_id, welcome_channel_id, welcome_data) VALUES(?,?,?)",
                (
                    interaction.guild.id,
                    self.channel_id,
                    str(data),
                ),
            )

            await interaction.message.delete()

            await interaction.send_success_message(
                title=f"Pomyślnie ustawiono przywitania {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Kanał przywitań został ustawiony.",
            )

        else:
            response: Optional[DB_RESPONSE] = await bot.db.execute_fetchone(
                "SELECT * FROM goodbyes WHERE guild_id = ?",
                (interaction.guild.id,),
            )

            if response:
                return await interaction.send_error_message(
                    description="Niestety, ale pożegnania już są ustawione."
                )

            data: tuple[str, ...] = (
                self.main_text,
                self.first_text,
                self.second_text,
            )

            await bot.db.execute_fetchone(
                "INSERT INTO goodbyes(guild_id, goodbye_channel_id, goodbye_data) VALUES(?,?,?)",
                (
                    interaction.guild.id,
                    self.channel_id,
                    str(data),
                ),
            )

            await interaction.send_success_message(
                title=f"Pomyślnie ustawiono pożegnania {Emojis.GREENBUTTON.value}",
                description=f"{Emojis.REPLY.value} Kanał pożegnań został ustawiony.",
            )

            await interaction.message.delete()

    async def update_image(self) -> File:
        main_text: str = self.main_text
        second_text: str = self.first_text
        third_text: str = self.second_text

        (
            main_text,
            second_text,
            third_text,
        ) = self.format_text(
            self.main_text,
            self.first_text,
            self.second_text,
        )

        user_avatar: str = self.interaction.user_avatar_url

        if not self.goodbye:
            background: Editor = Editor("./Data/images/welcome_image.jpg")
        else:
            background: Editor = Editor("./Data/images/goodbye_image.jpg")

        profile_image: Image.Image = await load_image_async(user_avatar)

        profile: Editor = Editor(profile_image).resize((400, 400)).circle_image()
        poppins = Font.poppins(size=90, variant="bold")

        poppins_medium = Font.poppins(size=65, variant="bold")
        poppins_small = Font.poppins(size=60, variant="light")

        background.paste(profile, (760, 170))
        background.ellipse(
            (760, 170),
            400,
            400,
            outline="#fff",
            stroke_width=4,
        )

        if not self.goodbye:
            background.text(
                (950, 610),
                f"{main_text}",
                color="#07f763",
                font=poppins,
                align="center",
            )
        else:
            background.text(
                (950, 610),
                f"{main_text}",
                color="#fc0828",
                font=poppins,
                align="center",
            )

        background.text(
            (950, 730),
            f"{second_text}",
            color="#fff",
            font=poppins_medium,
            align="center",
        )
        background.text(
            (950, 840),
            f"{third_text}",
            color="#e8dfdf",
            font=poppins_small,
            align="center",
        )

        if not self.goodbye:
            _file: File = File(
                fp=background.image_bytes,
                filename="welcomecard.jpg",
            )
        else:
            _file: File = File(
                fp=background.image_bytes,
                filename="goodbyecard.jpg",
            )

        return _file

    def format_text(
        self,
        main_text: str,
        first_text: str,
        second_text: str,
    ) -> tuple[str, ...]:
        assert isinstance(self.interaction.user, Member) and self.interaction.guild

        list_with_texts: list[str] = []

        for text in (
            main_text,
            first_text,
            second_text,
        ):
            list_with_texts.append(
                text.replace(
                    "{user}",
                    str(self.interaction.user),
                )
                .replace(
                    "{user_name}",
                    self.interaction.user.name,
                )
                .replace(
                    "{user_discriminator}",
                    f"#{self.interaction.user.discriminator}",
                )
                .replace(
                    "{user_id}",
                    str(self.interaction.user.id),
                )
                .replace(
                    "{guild_name}",
                    self.interaction.guild.name,
                )
                .replace(
                    "{guild_total_members}",
                    str(self.interaction.guild.member_count),
                )
                .replace(
                    "{guild_id}",
                    f"{self.interaction.guild.id}",
                )
            )

        return (
            list_with_texts[0][0:35],
            list_with_texts[1][0:45],
            list_with_texts[2][0:55],
        )


class CommandLobby(CustomCog):
    @slash_command(name="pożegnania", dm_permission=False)
    async def goodbye(self, interaction: CustomInteraction):
        pass

    @goodbye.subcommand(
        name="włącz",
        description="Ustawia pożegnania na serwerze.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def goodbye_on(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanał_powiadomień",
            description="Podaj kanał od pożegnań",
        ),
    ):
        await interaction.response.defer()

        main_text: str = "Główny tekst"
        second_text: str = "Pierwszy tekst"
        third_text: str = "Drugi tekst"

        background: Editor = Editor("./Data/images/goodbye_image.jpg")
        profile_image: Image.Image = await load_image_async(interaction.user_avatar_url)

        profile: Editor = Editor(profile_image).resize((400, 400)).circle_image()
        poppins = Font.poppins(size=90, variant="bold")

        poppins_medium = Font.poppins(size=65, variant="bold")
        poppins_small = Font.poppins(size=60, variant="light")

        background.paste(profile, (760, 170))
        background.ellipse(
            (760, 170),
            400,
            400,
            outline="#fff",
            stroke_width=4,
        )

        background.text(
            (950, 610),
            f"{main_text}",
            color="#fc0828",
            font=poppins,
            align="center",
        )
        background.text(
            (950, 720),
            f"{second_text}",
            color="#fff",
            font=poppins_medium,
            align="center",
        )
        background.text(
            (950, 805),
            f"{third_text}",
            color="#e8dfdf",
            font=poppins_small,
            align="center",
        )

        _file: File = File(
            fp=background.image_bytes,
            filename="goodbyecard.jpg",
        )

        description: str = """ **Dostępne atrybuty:**

- `{user}` = Nazwa użytkownika + hasztag
- `{user_name}` = Nazwa użytkownika
- `{user_discriminator}` = Hasztag użytkownika
- `{user_id}` = ID Użytkownika
- `{guild_name}` = Nazwa serwera
- `{guild_total_members}` = Liczba wszystkich użytkowników
- `{guild_id}` = ID Serwera

`⛔` Wszystkie atrybuty zamienią się z danymi osoby która wychodzi z serwera.

## Obraz podglądowy:
"""
        embed = Embed(
            title="`🔧` Edytowanie obrazku pożegnania",
            color=Color.red(),
            description=Emojis.REPLY.value + description,
            timestamp=utils.utcnow(),
        )
        embed.set_image(url="attachment://goodbyecard.jpg")
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        buttons = EditButtons(embed, interaction, channel.id, True)
        await interaction.send(file=_file, embed=embed, view=buttons)

    @goodbye.subcommand(
        name="wyłącz",
        description="Wyłacz pożegnania na serwerze!",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def goodbye_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM goodbyes WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(description="Pożegnania nie są włączone.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM goodbyes WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        return await interaction.send_success_message(
            title=f"Pomyślnie wyłączono pożegnania {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Pożegnania zostały wyłączone.",
        )

    @slash_command(name="przywitania", dm_permission=False)
    async def welcome(self, interaction: CustomInteraction) -> None:
        pass

    @welcome.subcommand(
        name="włącz",
        description="Ustawia przywitania na serwerze.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def welcome_on(
        self,
        interaction: CustomInteraction,
        channel: TextChannel = SlashOption(
            name="kanał_przywitań",
            description="Podaj kanał od przywitań",
        ),
    ) -> None:
        await interaction.response.defer()

        main_text: str = "Główny tekst"
        second_text: str = "Pierwszy tekst"
        third_text: str = "Drugi tekst"

        background: Editor = Editor("./Data/images/welcome_image.jpg")

        profile_image = await load_image_async(interaction.user_avatar_url)

        profile: Editor = Editor(profile_image).resize((400, 400)).circle_image()
        poppins = Font.poppins(size=90, variant="bold")

        poppins_medium = Font.poppins(size=65, variant="bold")
        poppins_small = Font.poppins(size=60, variant="light")

        background.paste(profile, (760, 170))
        background.ellipse(
            (760, 170),
            400,
            400,
            outline="#fff",
            stroke_width=4,
        )

        background.text(
            (950, 610),
            f"{main_text}",
            color="#07f763",
            font=poppins,
            align="center",
        )
        background.text(
            (950, 720),
            f"{second_text}",
            color="#fff",
            font=poppins_medium,
            align="center",
        )
        background.text(
            (950, 805),
            f"{third_text}",
            color="#e8dfdf",
            font=poppins_small,
            align="center",
        )

        _file = File(
            fp=background.image_bytes,
            filename="welcomecard.jpg",
        )

        description: str = """ **Dostępne atrybuty:**

- `{user}` = Nazwa użytkownika + hasztag
- `{user_name}` = Nazwa użytkownika
- `{user_discriminator}` = Hasztag użytkownika
- `{user_id}` = ID Użytkownika
- `{guild_name}` = Nazwa serwera
- `{guild_total_members}` = Liczba wszystkich użytkowników
- `{guild_id}` = ID Serwera

`⛔` Wszystkie atrybuty zamienią się z danymi osoby która wchodzi na serwer.

## Obraz podglądowy:
"""
        embed = Embed(
            title="`🔧` Edytowanie obrazku przywitania",
            color=Color.dark_theme(),
            description=Emojis.REPLY.value + description,
            timestamp=utils.utcnow(),
        )

        embed.set_footer(
            text=f"Smiffy v{self.bot.__version__}",
            icon_url=self.bot.avatar_url,
        )
        embed.set_image(url="attachment://welcomecard.jpg")
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user_avatar_url,
        )

        buttons = EditButtons(embed, interaction, channel.id)
        await interaction.send(file=_file, embed=embed, view=buttons)

    @welcome.subcommand(
        name="wyłącz",
        description="Wyłącza aktualne przywitania.",
    )  # pyright: ignore
    @PermissionHandler(manage_guild=True)
    async def welcome_off(self, interaction: CustomInteraction):
        assert interaction.guild

        response: Optional[DB_RESPONSE] = await self.bot.db.execute_fetchone(
            "SELECT * FROM welcomes WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        if not response:
            return await interaction.send_error_message(description="Przywitania już są wyłączone.")

        await self.bot.db.execute_fetchone(
            "DELETE FROM welcomes WHERE guild_id = ?",
            (interaction.guild.id,),
        )

        await interaction.send_success_message(
            title=f"Pomyślnie wyłączono przywitania {Emojis.GREENBUTTON.value}",
            description=f"{Emojis.REPLY.value} Przywitania zostały wyłączone.",
        )


def setup(bot: Smiffy):
    bot.add_cog(CommandLobby(bot))
